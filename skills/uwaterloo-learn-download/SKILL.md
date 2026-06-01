---
name: uwaterloo-learn-download
description: Use when the user asks to download, sync, or update course files or announcements from UWaterloo Learn (learn.uwaterloo.ca).
---

# UWaterloo Learn Content Downloader

## Overview

Downloads UWaterloo Learn/Brightspace course materials into a local workspace. Files go directly into `<root>/<COURSE_SLUG>/...` — no duplicate mirror. A `_manifest.json` tracks each file's Learn-origin hash to protect user-modified files from being overwritten.

## Workflow

Run these phases in order:

1. **Pre-Fetch Audit** — Identify user-owned files before touching anything
2. **Authentication** — Export Learn-only cookies via browser-use
3. **Course Selection** — Show discovered courses, let user choose which to fetch
4. **Fetch** — Run `fetch_learn_materials.py` on selected courses only
5. **Post-Fetch** — Review output, reconcile conflicts, check external candidates

---

## Running the Downloader

Stable entrypoint — do not create one-off workspace scripts:

```bash
python3 <skill-dir>/scripts/fetch_learn_materials.py --root /path/to/workspace
```

Files go to `<root>/<COURSE_SLUG>/...`. Sync metadata goes to `<root>/_sync/<COURSE_SLUG>/`. Manifest at `<root>/_manifest.json`.

Course discovery (default):
```
GET /d2l/api/lp/1.28/enrollments/myenrollments/?orgUnitTypeId=3
```

Targeted refresh:
```bash
python3 .../fetch_learn_materials.py --root /path/to/workspace --only COURSE_SLUG
```

Fixed course list (only when the caller explicitly needs it):
```bash
python3 .../fetch_learn_materials.py --root /path/to/workspace --courses-json /path/to/courses.json
```

---

## Course Selection

> **STOP. Do not run the downloader yet.**
>
> After cookie export, you MUST: call the enrollment API → show courses to the user → wait for their answer → only then run the script.
> Jumping straight from cookie export to `fetch_learn_materials.py` is a violation.

### Step 1: Discover courses and compute folder names

The script's `course_slug()` logic determines the actual folder name — not the raw API `Code`. Run this snippet to get both:

```python
import json, re, requests

def course_slug(code, name, ou):
    text = code or name or str(ou)
    m = re.search(r"([A-Z]{2,}\s*\d{3}[A-Z]?)", text, re.I)
    if m:
        return m.group(1).upper().replace(" ", "")
    return re.sub(r"[_\s-]+", "_", text.split("_")[0]) or str(ou)

cookies = {c["name"]: c["value"] for c in json.load(open("/tmp/learn_cookies.json"))}
resp = requests.get(
    "https://learn.uwaterloo.ca/d2l/api/lp/1.28/enrollments/myenrollments/",
    params={"orgUnitTypeId": 3},
    cookies=cookies,
)
seen = {}
rows = []
for item in resp.json().get("Items", []):
    org = item.get("OrgUnit", item)
    ou = org.get("Id")
    slug = course_slug(org.get("Code", ""), org.get("Name", ""), ou)
    if slug in seen:
        slug = f"{slug}_{ou}"   # same dedup logic as the script
    seen[slug] = True
    rows.append({"folder": slug, "name": org.get("Name", ""), "code": org.get("Code", "")})

for r in rows:
    print(f"  {r['folder']:30s}  {r['name']}")
```

The `folder` column is what will appear on disk. Show this to the user, not the raw API code.

### Step 2: Classify before showing

**Normal** — folder matches bare `[A-Z]+\d+` (e.g. `ECE327`, `MATH213`).

**Unusual** — flag for clarification if any of:
- Folder has a numeric/hash suffix: `ECE318_1277913`
- Looks like an admin/community org: `Engineering_Co_op_Community`, `WINTER202`
- Does not match `[A-Z]+\d+` at all

### Step 3: Show the list and WAIT for user confirmation

```
Found N courses on Learn:

  Folder    Name
  ────────────────────────────────────────────────
  ECE318    ECE 318 (Lecture)
  ECE318_<ou>  ECE 318 Lab          ← duplicate folder, clarify?
  ECE327    ECE 327
  ECE350    ECE 350
  ECE380    ECE 380 (Lecture)
  ECE380_<ou>  ECE 380 (Lab)        ← duplicate folder, clarify?
  MATH135   MATH 135 Online
  PSYCH207  PSYCH 207 Online

Unusual — skip or keep?
  Engineering_Co_op_Community  — admin org?
  WINTER202                    — term org unit?

Fetch all normal courses, or list specific folders you want?
```

**Wait for the user's reply. Do not run anything until they respond.**

### Step 4: Run the downloader with their selection

- **"all"** → run without `--only`
- **Specific folders** → pass `--only FOLDER` for each (use the `folder` value, not the API code)
- **"none"** → abort, do not run the downloader

---

## Hard Rules

- **Learn-only cookies.** Only export cookies from `learn.uwaterloo.ca` or subdomains. Never commit cookies.
- **Store cookies in `/tmp/learn_cookies.json`.** Never commit.
- **Close browser-use when done.** Run `browser-use close` + verify `browser-use sessions` shows no active sessions.
- **Never delete or edit `_manifest.json` manually.**
- **No hardcoded course IDs, folder names, or term assumptions** in the general workflow.
- **NEVER run the downloader immediately after getting cookies.** After authentication, you MUST call the enrollment API yourself, show the course list to the user, and wait for their confirmation. Only then run the script. Skipping straight to `fetch_learn_materials.py` after cookie export is a violation.

---

## Pre-Fetch: User File Audit

Run before any authentication or fetch step.

### Step 1: Check USER_NOTED_FILES.md

```bash
test -f <workspace>/USER_NOTED_FILES.md && echo "exists" || echo "missing"
```

If it exists: read it, extract "Confirmed Protected Files" and "Likely User Notes To Preserve". Then proceed to Step 2 to catch any files not yet listed.

If missing (cold start): skip to Step 2.

### Step 2: Heuristic Scan

```bash
ls <workspace>/
find <workspace> -mindepth 2 -type f \
  -not -path '<workspace>/_sync/*' \
  -not -path '<workspace>/.git/*'
cat <workspace>/_manifest.json 2>/dev/null
```

Classify as **candidate protected** if any of:
1. Not in `_manifest.json` — never fetched from Learn
2. In manifest but `sha256(current) != learn_hash` — user-modified
3. Timestamped filename (e.g. `name 2026-05-14 17_34_32.ext`)

Do not use filename keyword lists. Use the manifest as the primary signal.

### Step 3: Confirm With User

**Cold start (no manifest, no USER_NOTED_FILES.md):**
```
Pre-fetch scan found the following files in your course folders.
Which of these contain your own work (annotations, notes, edits)?

  ECE327/Lectures/
    - 02-ece327-s2026-systemverilog-basics-I.pdf  (545 KB)
    - 04-ece327-s2026-design-case-studies.pdf     (1.7 MB)

  ECE380/4. First and Second Order Systems/
    - CH4_Notes.md

Which are yours? (say "all", "none", or list specific paths)
```

Wait for response. Create `USER_NOTED_FILES.md` with confirmed files under "Confirmed Protected Files", then proceed.

**Returning user — new candidates found:**
```
Pre-fetch audit: N files already protected.

New files found that may be yours:
  - ECE350/Lectures/02-concepts.pdf  (13 MB, not in manifest)

Are any of these yours? (y/n per file)
```

Wait for response. Update `USER_NOTED_FILES.md`, then proceed.

**Returning user — no new candidates:** proceed silently.

---

## Authentication And Cookie Export

1. Detect local Chrome profiles:
```bash
browser-use profile list
```

2. Open Learn with the detected profile (do not hardcode the profile name):
```bash
browser-use --headed --profile "<detected Chrome profile>" open https://learn.uwaterloo.ca
browser-use state
```

3. If state still shows Microsoft/ADFS login, have the user complete login/Duo in the visible window, then re-run `browser-use state`. Continue only when state shows the Learn home page or course list.

4. Export and filter to Learn-only cookies:
```bash
browser-use cookies export --url https://learn.uwaterloo.ca /tmp/learn_cookies_raw.json
```

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

---

## Browser Cleanup

Always before finishing any workflow that opened browser-use:

```bash
browser-use close
browser-use sessions
```

Expected output:
```
No active sessions
```

Do not leave a headed Chrome session running in the background.

---

## Manifest Protection

Each fetched file is tracked in `_manifest.json` under `<COURSE_SLUG>/<relative-path>`:

```json
{
  "learn_hash": "<sha256 at fetch time>",
  "server_mtime": "<LastModifiedDate from Learn API>"
}
```

| File State | Action |
|------------|--------|
| Missing | Download, write manifest entry |
| Not in manifest | Protected-skip (user-created file) |
| In manifest, hash matches, server unchanged | Skip |
| In manifest, hash matches, server changed | Overwrite, update manifest |
| In manifest, hash differs, server unchanged | Modified-skip (user edited, Learn same) |
| In manifest, hash differs, server changed | **Conflict**: download Learn's version to `/tmp/learn_new_<filename>`, emit conflict event |

The conflict case is the only one where a second copy temporarily exists.

---

## External Course Webpages

Some courses keep real materials on an external page linked from Learn announcements or TOC. Do not solve this with hardcoded hostnames or keyword lists.

1. Script writes external link candidates + surrounding context to `_sync/<COURSE_SLUG>/_external_candidates.json`
2. AI reads the candidates; opens pages with `browser-use` when needed
3. AI selects the real material source by semantic understanding
4. Run with the selected page:

```bash
python3 .../fetch_learn_materials.py \
  --root /path/to/workspace \
  --only COURSE_SLUG \
  --external-page 'COURSE_SLUG=https://example.com/course/page|Course Materials'
```

Downloads only direct file links: `.pdf`, `.pptx`, `.docx`, `.xlsx`, `.zip`, `.ipynb`, `.txt`, `.csv`.

---

## Post-Fetch Checks

After every fetch:
- Check output for errors
- Review `modified-skip` and `protected-skip` events
- Review `conflict` events — require immediate reconciliation (see below)
- Inspect `_sync/<COURSE_SLUG>/_external_candidates.json` when a course may use external pages

### Conflict Reconciliation

For each conflict event:
```
---- Conflict: ECE327/Lectures/04-ece327-s2026-design-case-studies.pdf ----

  Your copy:   ECE327/Lectures/04-ece327-s2026-design-case-studies.pdf
  Learn copy:  /tmp/learn_new_04-ece327-s2026-design-case-studies.pdf

  Sizes:  yours: 14.2 MB  |  Learn: 8.1 MB

Options:
  (a) Keep your version. Discard the Learn copy from /tmp/.
  (b) Replace with Learn's version. Your copy is overwritten.
  (c) Keep both. Learn's version moved to <course>/<name>_learn_new.<ext>.

Your choice (a/b/c)?
```

Default if no response: **(a)**. Never silently overwrite a user-modified file.

Actions:
- **(a):** `rm /tmp/learn_new_<filename>`. Clear `server_mtime` in manifest so next fetch re-evaluates.
- **(b):** `mv /tmp/learn_new_<filename> <dest>`. Update manifest with new hash and mtime.
- **(c):** `mv /tmp/learn_new_<filename> <course>/<name>_learn_new.<ext>`. Append note to `USER_NOTED_FILES.md` under "## Pending Manual Review".

After all conflicts resolved, print summary:
```
Reconciliation complete.
  ECE327/Lectures/04-ece327-s2026-design-case-studies.pdf  → kept your copy
  ECE318/Lecture Slides/chapter3a.pdf                      → kept both (review manually)

No protected files were overwritten.
```

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Exporting cookies from all domains | Filter to `learn.uwaterloo.ca` only before writing `/tmp/learn_cookies.json` |
| Leaving browser-use session open | Always run `browser-use close` + verify no active sessions |
| Editing or deleting `_manifest.json` | Read-only except by the script — it's the sync ledger |
| Hardcoding course slugs or IDs | Let the enrollment API discover courses dynamically |
| Creating workspace scripts instead of using the bundled one | Always use `fetch_learn_materials.py` from the skill directory |
| Skipping pre-fetch audit | Run it every time — new user files may have appeared since last fetch |
| Running the downloader right after cookie export | **STOP after authentication.** Call the enrollment API, show courses, wait for confirmation. Never go straight to `fetch_learn_materials.py`. |
| Fetching all courses without asking | Always show discovered courses and wait for user confirmation before running the downloader |

---

## Output Structure

```
workspace/
├── _manifest.json          ← sync ledger (learn_hash + server_mtime per file)
├── _sync/                  ← metadata only, no material files
│   ├── COURSE_A/
│   │   ├── _toc.json
│   │   └── _external_candidates.json
│   └── COURSE_B/
│       └── ...
├── COURSE_A/               ← material files live here directly
│   └── ...
└── COURSE_B/
    └── ...
```
