---
name: uwaterloo-learn-download
description: Use when downloading course content files or announcements from UWaterloo Learn/Brightspace (learn.uwaterloo.ca). Covers Learn-only cookie extraction, D2L enrollment discovery, content/API download, manifest protection, external material-page candidate discovery, and stable post-fetch checks.
---

# UWaterloo Learn Content Downloader

Use this skill to sync UWaterloo Learn/Brightspace course materials into a local workspace. The workflow is intended to be reusable across Waterloo students and terms: courses are discovered from the currently logged-in Learn account, not from hardcoded course IDs.

## Requirements

- Python 3.
- An authenticated Learn browser session.
- Learn-only cookies exported from that browser session.
- Browser automation such as `browser-use` is recommended for login verification and external course-page inspection.

## Stable Fetch Contract

This skill is the stable entrypoint for Learn fetch work. Do not create one-off workspace scripts when this skill applies. Use the bundled script from this skill directory:

```bash
python3 <skill-dir>/scripts/fetch_learn_materials.py --root /path/to/workspace
```

By default, the script writes `learn_content/` under `--root` and mirrors fetched files into matching course folders under `--root`.

By default, courses are discovered from Learn:

```text
GET /d2l/api/lp/1.28/enrollments/myenrollments/?orgUnitTypeId=3
```

Use `--courses-json /path/to/courses.json` only when the caller explicitly needs a fixed course list. Use `--only COURSE_SLUG` for targeted refreshes after dynamic discovery.

## Hard Rules

- Cookie export must only save cookies whose domain is `learn.uwaterloo.ca` or a subdomain of `learn.uwaterloo.ca`.
- Store exported Learn cookies in a local temp file such as `/tmp/learn_cookies.json`; never commit cookies.
- Fetch behavior must be consistent across runs: same bundled script, same manifest logic, same output structure.
- `learn_content/_manifest.json` is the authoritative sync ledger.
- Do not hardcode student-specific course IDs, folders, external webpages, or term assumptions into the general workflow.
- Discover external material pages from Learn announcements and TOC context, then let Codex/AI choose the real material source by semantic inspection.

## Authentication And Cookie Export

The downloader expects an authenticated Learn session. Prefer the user's local Chrome profile in headed mode so the login/Duo window is visible and the session matches what the user actually completed.

Reliable local approach:

1. Detect local Chrome profiles:

```bash
browser-use profile list
```

2. Open Learn with headed browser-use and the detected local Chrome profile. Do not hardcode a profile name; use the profile name returned by `browser-use profile list`.

```bash
browser-use --headed --profile "<detected Chrome profile>" open https://learn.uwaterloo.ca
browser-use state
```

3. If `browser-use state` still shows Microsoft/ADFS login, have the user complete login/Duo in the visible headed window, then re-run `browser-use state`. Continue only when the state shows the Learn home page or course list.

4. Export cookies from the logged-in headed session, then filter down to Learn-only cookies before writing `/tmp/learn_cookies.json`.

```bash
browser-use cookies export --url https://learn.uwaterloo.ca /tmp/learn_cookies_raw.json
```

Cookie filtering rule:

```python
import json

all_cookies = json.load(open("/tmp/learn_cookies_raw.json"))
cookies = [
    c for c in all_cookies
    if c.get("domain", "") == "learn.uwaterloo.ca"
    or c.get("domain", "").endswith(".learn.uwaterloo.ca")
]
json.dump(cookies, open("/tmp/learn_cookies.json", "w"), indent=2)
```

Do not export broad Waterloo, Google, Chrome profile, or unrelated site cookies.

## External Course Webpages

Some courses keep real materials on an external course webpage linked from Learn announcements or the Learn TOC. Do not solve this with hardcoded course names, hostnames, keyword blacklists, or keyword whitelists.

Stable workflow:

1. The script fetches each course's `news/` API and Learn TOC links.
2. It writes external link candidates plus surrounding context to:

```text
learn_content/<COURSE>/_external_candidates.json
```

3. Codex/AI reads the candidate context and, when useful, opens candidate pages with `browser-use`.
4. Codex/AI selects the real material source page by semantic understanding.
5. Run the same script with an AI-selected external page:

```bash
python3 <skill-dir>/scripts/fetch_learn_materials.py \
  --root /path/to/workspace \
  --only COURSE_SLUG \
  --external-page 'COURSE_SLUG=https://example.com/course/page|Course Materials'
```

The script downloads only direct material file links from selected pages, such as `.pdf`, `.pptx`, `.docx`, `.xlsx`, `.zip`, `.ipynb`, `.txt`, and `.csv`.

## Manifest Protection

Each downloaded file is tracked in `learn_content/_manifest.json` using its original SHA-256 hash and server modified time.

Behavior:

```text
file missing                         -> download
file exists but not in manifest       -> protected-skip
file hash differs from manifest hash  -> modified-skip
file hash matches and server unchanged -> unchanged
file hash matches and server changed  -> update
```

This protects local annotations, manually added files, and edited notes from being overwritten by a later sync.

## Post-Fetch Checks

After a fetch:

- Check command output for errors.
- Review `modified-skip` and `protected-skip` events before making any manual changes.
- Inspect `learn_content/<COURSE>/_external_candidates.json` when a course likely uses external material pages.
- If the workspace has timestamped annotated PDFs or local note-routing conventions, handle them with the workspace's own rules rather than adding those rules to this general skill.

## Output Structure

Typical workspace structure:

```text
workspace/
├── learn_content/
│   ├── _manifest.json
│   ├── COURSE_A/
│   │   ├── _toc.json
│   │   └── ...
│   └── COURSE_B/
│       └── ...
├── COURSE_A/
└── COURSE_B/
```

The `learn_content/` tree is the fetch ledger and source mirror; course folders under the workspace are convenience mirrors for daily use.
