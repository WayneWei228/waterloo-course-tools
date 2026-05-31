#!/usr/bin/env python3
import argparse
import hashlib
import html
import html.parser
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE_URL = "https://learn.uwaterloo.ca"
MATERIAL_EXTENSIONS = {
    ".pdf",
    ".ppt",
    ".pptx",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".zip",
    ".ipynb",
    ".txt",
    ".csv",
}

class LinkExtractor(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._href_stack = []
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            attrs = dict(attrs)
            href = attrs.get("href")
            if href:
                self._href_stack.append(href)
                self._text.append("")

    def handle_data(self, data):
        if self._href_stack:
            self._text[-1] += data

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href_stack:
            href = self._href_stack.pop()
            text = self._text.pop()
            self.links.append((href, re.sub(r"\s+", " ", html.unescape(text)).strip()))


def sanitize(name):
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip().rstrip(".") or "Untitled"


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_cookies(cookie_file):
    raw = json.loads(cookie_file.read_text())
    cookies = []
    for c in raw:
        domain = c.get("domain", "")
        if domain == "learn.uwaterloo.ca" or domain.endswith(".learn.uwaterloo.ca"):
            cookies.append(f"{c['name']}={c['value']}")
    return "; ".join(cookies)


def request(url, cookie, accept="*/*"):
    return http_request(url, cookie=cookie, accept=accept, base_url=BASE_URL)


def http_request(url, cookie="", accept="*/*", base_url=""):
    full_url = urllib.parse.urljoin(BASE_URL, url)
    if base_url:
        full_url = urllib.parse.urljoin(base_url, url)
    else:
        full_url = url
    parsed = urllib.parse.urlsplit(full_url)
    full_url = urllib.parse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            urllib.parse.quote(parsed.path, safe="/%:@"),
            urllib.parse.quote(parsed.query, safe="=&?/:@%+"),
            urllib.parse.quote(parsed.fragment, safe="=&?/:@%+"),
        )
    )
    req = urllib.request.Request(
        full_url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": accept,
        },
    )
    if cookie:
        req.add_header("Cookie", cookie)
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read()


def load_manifest(path):
    if path.exists():
        return json.loads(path.read_text())
    return {}


def save_manifest(path, manifest):
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


def topic_filename(topic):
    title = sanitize(topic.get("Title", "Untitled"))
    url = topic.get("Url") or ""
    parsed = urllib.parse.urlparse(url)
    suffix = Path(urllib.parse.unquote(parsed.path)).suffix

    if topic.get("TypeIdentifier") == "File":
        return title if suffix and title.endswith(suffix) else title + (suffix or ".bin")
    if topic.get("TypeIdentifier") in {"Link", "LtiLink"}:
        return title + ".url"
    return title + ".html"


def topic_payload(topic, cookie):
    url = topic.get("Url") or ""
    typ = topic.get("TypeIdentifier")

    if typ == "File":
        return request(url, cookie)

    if typ in {"Link", "LtiLink"}:
        target = urllib.parse.urljoin(BASE_URL, url)
        return f"[InternetShortcut]\nURL={target}\n".encode()

    if url.startswith(("http://", "https://", "/")):
        try:
            return request(url, cookie, accept="text/html,*/*")
        except Exception:
            target = urllib.parse.urljoin(BASE_URL, url)
            body = f'<p><a href="{html.escape(target)}">{html.escape(target)}</a></p>\n'
            return body.encode()

    body = (
        "<!doctype html>\n<meta charset=\"utf-8\">\n"
        f"<title>{html.escape(topic.get('Title', 'Untitled'))}</title>\n"
        f"<p>{html.escape(url)}</p>\n"
    )
    return body.encode()


def iter_topics(modules, prefix=()):
    for module in modules:
        title = sanitize(module.get("Title", "Untitled"))
        current = prefix + (title,)
        for topic in module.get("Topics", []):
            yield current, topic
        yield from iter_topics(module.get("Modules", []), current)


def write_if_allowed(dest, payload, original_hash):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and original_hash and sha256(dest) != original_hash:
        return "modified-skip"
    if dest.exists() and dest.read_bytes() == payload:
        return "unchanged"
    dest.write_bytes(payload)
    return "written"


def load_courses(path):
    if not path:
        raise ValueError("--courses-json is required when loading explicit courses")
    raw = json.loads(path.read_text())
    if isinstance(raw, dict):
        return {str(k): int(v) for k, v in raw.items()}
    return {str(item["name"]): int(item["ou"]) for item in raw}


def parse_external_page(spec):
    course, rest = spec.split("=", 1)
    if "|" in rest:
        url, label = rest.split("|", 1)
    else:
        url = rest
        label = "External Course Page"
    return course, url, label


def course_slug(code, name, ou):
    text = code or name or str(ou)
    match = re.search(r"([A-Z]{2,}\s*\d{3}[A-Z]?)", text, re.I)
    if match:
        return sanitize(match.group(1).upper().replace(" ", ""))
    return sanitize(re.sub(r"[_\s-]+", "_", text.split("_")[0])) or str(ou)


def discover_courses(cookie):
    payload = request(
        "/d2l/api/lp/1.28/enrollments/myenrollments/?orgUnitTypeId=3",
        cookie,
        accept="application/json",
    )
    data = json.loads(payload)
    items = data.get("Items", data if isinstance(data, list) else [])
    courses = {}
    for item in items:
        org = item.get("OrgUnit", item)
        ou = org.get("Id")
        if not ou:
            continue
        slug = course_slug(org.get("Code", ""), org.get("Name", ""), ou)
        if slug in courses:
            slug = f"{slug}_{ou}"
        courses[slug] = int(ou)
    return courses


def extract_links(markup, base_url):
    parser = LinkExtractor()
    parser.feed(markup)
    seen = set()
    out = []
    for href, text in parser.links:
        url = urllib.parse.urljoin(base_url, href)
        if url in seen:
            continue
        seen.add(url)
        out.append((url, text))
    return out


def html_text(markup):
    text = re.sub(r"<[^>]+>", " ", markup)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def link_contexts(markup, base_url):
    out = []
    for match in re.finditer(r"<a\b[^>]*\bhref=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", markup, re.I | re.S):
        href = match.group(1)
        anchor = html_text(match.group(2))
        block_start = max(markup.rfind("<p", 0, match.start()), markup.rfind("<li", 0, match.start()), markup.rfind("<div", 0, match.start()))
        if block_start == -1:
            block_start = max(0, match.start() - 120)
        block_end_candidates = [
            pos for pos in (
                markup.find("</p>", match.end()),
                markup.find("</li>", match.end()),
                markup.find("</div>", match.end()),
            )
            if pos != -1
        ]
        block_end = min(block_end_candidates) + 6 if block_end_candidates else min(len(markup), match.end() + 120)
        context = html_text(markup[block_start:block_end])
        out.append((urllib.parse.urljoin(base_url, href), anchor, context))
    return out


def is_direct_material(url):
    path = urllib.parse.urlparse(url).path.lower()
    return Path(path).suffix in MATERIAL_EXTENSIONS


def external_filename(url, text):
    parsed = urllib.parse.urlparse(url)
    suffix = Path(urllib.parse.unquote(parsed.path)).suffix
    stem = Path(urllib.parse.unquote(parsed.path)).name
    if stem and suffix:
        return sanitize(stem)
    label = sanitize(text) if text else sanitize(parsed.netloc + parsed.path)
    return label + (suffix or ".html")


def write_tracked(output_dir, root, rel, mirror_rel, payload, mtime, manifest, events):
    key = str(rel)
    existing = manifest.get(key, {})
    learn_dest = output_dir / rel
    course_dest = root / mirror_rel

    if learn_dest.exists() and existing.get("hash") and sha256(learn_dest) != existing["hash"]:
        events.append(("modified-skip", key))
        return

    payload_hash = hashlib.sha256(payload).hexdigest()
    if existing.get("hash") == payload_hash and learn_dest.exists():
        if not course_dest.exists():
            course_dest.parent.mkdir(parents=True, exist_ok=True)
            course_dest.write_bytes(learn_dest.read_bytes())
            events.append(("mirrored", str(course_dest.relative_to(root))))
        return

    learn_dest.parent.mkdir(parents=True, exist_ok=True)
    learn_dest.write_bytes(payload)
    manifest[key] = {"hash": payload_hash, "server_mtime": mtime}
    events.append(("new" if not existing else "updated", key))

    mirror_status = write_if_allowed(course_dest, payload, existing.get("hash"))
    if mirror_status != "unchanged":
        events.append((mirror_status, str(course_dest.relative_to(root))))


def sync_external_pages(root, output_dir, name, source_pages, manifest, events):
    seen_pages = set()
    for page_url, page_text in source_pages:
        if page_url in seen_pages:
            continue
        seen_pages.add(page_url)
        try:
            page = http_request(page_url, accept="text/html,*/*", base_url=page_url)
        except Exception as e:
            events.append((f"external-page-error-{type(e).__name__}", f"{name}: {page_url}"))
            continue

        parsed = urllib.parse.urlparse(page_url)
        page_dir = Path(name, "External Course Webpages", sanitize(parsed.netloc), sanitize(page_text))
        mirror_dir = Path(name, "External Course Webpages", sanitize(parsed.netloc), sanitize(page_text))
        write_tracked(
            output_dir,
            root,
            page_dir / "index.html",
            mirror_dir / "index.html",
            page,
            page_url,
            manifest,
            events,
        )

        for material_url, text in extract_links(page.decode("utf-8", "replace"), page_url):
            if not is_direct_material(material_url):
                continue
            try:
                payload = http_request(material_url, accept="*/*", base_url=page_url)
            except Exception as e:
                events.append((f"external-file-error-{type(e).__name__}", f"{name}: {material_url}"))
                continue
            rel = page_dir / external_filename(material_url, text)
            mirror_rel = mirror_dir / external_filename(material_url, text)
            write_tracked(output_dir, root, rel, mirror_rel, payload, material_url, manifest, events)


def sync_external_sources(output_dir, name, ou, cookie, toc, events):
    candidates = []
    try:
        news = json.loads(request(f"/d2l/api/le/1.75/{ou}/news/", cookie, accept="application/json"))
    except Exception as e:
        events.append((f"news-error-{type(e).__name__}", name))
        news = []

    for item in news:
        body = (item.get("Body") or {}).get("Html") or ""
        for url, text, context in link_contexts(body, BASE_URL):
            candidates.append(
                {
                    "source": "announcement",
                    "announcement_title": item.get("Title", ""),
                    "url": url,
                    "anchor_text": text,
                    "context": context,
                }
            )

    for _, topic in iter_topics(toc.get("Modules", [])):
        if topic.get("TypeIdentifier") not in {"Link", "LtiLink"}:
            continue
        url = topic.get("Url") or ""
        if not url.startswith(("http://", "https://")):
            continue
        candidates.append(
            {
                "source": "toc",
                "topic_title": topic.get("Title", ""),
                "url": url,
                "anchor_text": topic.get("Title", ""),
                "context": topic.get("Description", {}).get("Text", "") if isinstance(topic.get("Description"), dict) else "",
            }
        )

    course_out = output_dir / name
    course_out.mkdir(parents=True, exist_ok=True)
    (course_out / "_external_candidates.json").write_text(
        json.dumps(candidates, indent=2, ensure_ascii=False) + "\n"
    )
    if candidates:
        events.append(("external-candidates", f"{name}: {len(candidates)}"))


def sync_course(root, output_dir, name, ou, cookie, manifest, events):
    toc_bytes = request(f"/d2l/api/le/1.75/{ou}/content/toc", cookie, accept="application/json")
    toc = json.loads(toc_bytes)

    course_out = output_dir / name
    course_out.mkdir(parents=True, exist_ok=True)
    (course_out / "_toc.json").write_bytes(json.dumps(toc, indent=2, ensure_ascii=False).encode() + b"\n")

    course_root = root / name
    course_root.mkdir(parents=True, exist_ok=True)

    for module_parts, topic in iter_topics(toc.get("Modules", [])):
        if topic.get("IsHidden") or topic.get("IsLocked"):
            continue

        rel = Path(name, *module_parts, topic_filename(topic))
        key = str(rel)
        server_mtime = topic.get("LastModifiedDate", "")
        existing = manifest.get(key, {})
        learn_dest = output_dir / rel
        course_dest = course_root / Path(*module_parts, topic_filename(topic))

        if learn_dest.exists() and existing.get("hash"):
            if sha256(learn_dest) != existing["hash"]:
                events.append(("modified-skip", key))
                continue
            if server_mtime == existing.get("server_mtime"):
                if not course_dest.exists():
                    course_dest.parent.mkdir(parents=True, exist_ok=True)
                    course_dest.write_bytes(learn_dest.read_bytes())
                    events.append(("mirrored", str(course_dest.relative_to(root))))
                continue

        try:
            payload = topic_payload(topic, cookie)
        except urllib.error.HTTPError as e:
            events.append((f"error-{e.code}", key))
            continue
        except Exception as e:
            events.append((f"error-{type(e).__name__}", key))
            continue

        learn_dest.parent.mkdir(parents=True, exist_ok=True)
        learn_dest.write_bytes(payload)
        new_hash = sha256(learn_dest)
        status = "new" if not existing else "updated"
        manifest[key] = {"hash": new_hash, "server_mtime": server_mtime}
        events.append((status, key))

        mirror_status = write_if_allowed(course_dest, payload, existing.get("hash"))
        if mirror_status != "unchanged":
            events.append((mirror_status, str(course_dest.relative_to(root))))

    sync_external_sources(output_dir, name, ou, cookie, toc, events)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--cookie-file", type=Path, default=Path("/tmp/learn_cookies.json"))
    parser.add_argument("--courses-json", type=Path)
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help="Only sync courses whose discovered/generated slug matches this value. Can be repeated.",
    )
    parser.add_argument(
        "--external-page",
        action="append",
        default=[],
        metavar="COURSE=URL|LABEL",
        help="Download direct material files from an AI-selected external course page.",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    output_dir = (args.output_dir or root / "learn_content").resolve()
    manifest_path = output_dir / "_manifest.json"

    if not args.cookie_file.exists():
        print(f"missing cookie file: {args.cookie_file}", file=sys.stderr)
        return 2
    cookie = load_cookies(args.cookie_file)
    if not cookie:
        print("no learn.uwaterloo.ca cookies found", file=sys.stderr)
        return 2

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(manifest_path)
    events = []

    try:
        courses = load_courses(args.courses_json) if args.courses_json else discover_courses(cookie)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    if args.only:
        wanted = {item.lower() for item in args.only}
        courses = {name: ou for name, ou in courses.items() if name.lower() in wanted}
        missing = sorted(wanted - {name.lower() for name in courses})
        if missing:
            print(f"no matching discovered courses for --only: {', '.join(missing)}", file=sys.stderr)
            return 2

    for name, ou in courses.items():
        sync_course(root, output_dir, name, ou, cookie, manifest, events)

    for spec in args.external_page:
        try:
            course, url, label = parse_external_page(spec)
        except ValueError:
            print(f"invalid --external-page value: {spec}", file=sys.stderr)
            return 2
        sync_external_pages(root, output_dir, course, [(url, label)], manifest, events)

    save_manifest(manifest_path, manifest)

    counts = {}
    for status, _ in events:
        counts[status] = counts.get(status, 0) + 1

    print(json.dumps({"counts": counts, "events": events}, indent=2, ensure_ascii=False))
    return 1 if any(status.startswith("error-") for status, _ in events) else 0


if __name__ == "__main__":
    raise SystemExit(main())
