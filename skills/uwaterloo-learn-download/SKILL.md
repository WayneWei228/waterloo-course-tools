---
name: uwaterloo-learn-download
description: Use when the user asks to download, sync, or update course files or announcements from UWaterloo Learn (learn.uwaterloo.ca).
---

# UWaterloo Learn Content Downloader

## Overview

Downloads UWaterloo Learn/Brightspace course materials into a local workspace. Files go directly into `<root>/<COURSE_SLUG>/...` — no duplicate mirror. A `_manifest.json` tracks each file's Learn-origin hash to protect user-modified files from being overwritten.

## Workflow

Run these phases in order:

1. **Sync Preferences** — Read or generate `SYNC_PREFERENCES.md` before anything else
2. **Pre-Fetch Audit** — Identify user-owned files before touching anything
3. **Authentication** — Export Learn-only cookies via browser-use
4. **Course Selection** — Show discovered courses, let user choose which to fetch
5. **Fetch** — Run `fetch_learn_materials.py` on selected courses only
6. **Post-Fetch Placement** — Move fetched files to destinations from `SYNC_PREFERENCES.md`
7. **Post-Fetch Checks** — Review output, reconcile conflicts, check external candidates

---

## Sync Preferences

> **STOP. Read this section before doing anything else.**
>
> `SYNC_PREFERENCES.md` is the authoritative mapping from Learn API slugs to local folder destinations. It must exist (or be created) before any files are placed.

### Step 1: Check for existing preferences

```bash
test -f <workspace>/SYNC_PREFERENCES.md && echo "exists" || echo "missing"
```

**If it exists:** read the full file now. Extract the course-to-folder mapping table and any special placement notes. These rules override all defaults for the entire session.

**If missing:** proceed to Step 2 to create it.

### Step 2 (first run only): Discover courses and ask user

After authentication and course discovery (see Course Selection below), present the discovered courses and ask the user where each should go:

```
I found these courses on Learn. Before fetching, I need to know how to
organize the files locally. Please confirm the local folder for each:

  Learn Slug                          Suggested Local Folder
  ──────────────────────────────────────────────────────────
  ECE318_wzhuang_002_1265             ECE318/
  ECE318_hnafissi_1265                ECE318/Lab Information/  ← lab section?
  ECE327_a2boutro_1265                ECE327/
  ...

Are these folder assignments correct? Any courses that should go somewhere
else, or any sub-folder rules (e.g. lab content under a specific subfolder)?
```

Wait for user confirmation or corrections. Also ask:
- Are any two slugs for the same course (lecture + lab)? If so, which subfolder for the lab content?
- Are there any slugs that look like admin/co-op orgs to skip entirely?

### Step 3: Generate SYNC_PREFERENCES.md

Create `<workspace>/SYNC_PREFERENCES.md` using the user's answers. Use this template:

```markdown
# Learn Sync Preferences

> **Before placing any fetched file:** read this document first to determine
> the correct local destination. Do not default to the Learn API slug as the
> folder name — the mapping below is authoritative.

## Course → Local Folder Mapping

| Learn API Slug | Local Folder | Notes |
|---|---|---|
| `SLUG_A` (id: XXXXXX) | `COURSE/` | Lecture |
| `SLUG_B` (id: XXXXXX) | `COURSE/Lab Materials/` | Lab — content goes here |

## Notes on Specific Courses

### Lab Courses
[Any special handling, e.g. ECE318 Lab content lives under ECE318/Lab Information/]

## Skipped Orgs

These are admin/co-op orgs — always skip:
- `OrgName` (id: XXXXXX)

## Courses JSON

Stable courses JSON for `--courses-json` flag: `_sync/courses.json`
```

After writing the file, confirm with the user: "I've created `SYNC_PREFERENCES.md`. You can edit it anytime to change where files are placed."

### Step 4: Enforce during post-fetch placement

After fetching, use the mapping in `SYNC_PREFERENCES.md` to determine where each file goes. The script places files under `<root>/<API_SLUG>/...` by default — after fetch, move or copy files to the correct destinations per the mapping.

For any slug not listed in `SYNC_PREFERENCES.md`, stop and ask the user before placing files.

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

Import `discover_courses` directly from the script — do not duplicate its logic:

```python
import json, sys
sys.path.insert(0, "<skill-dir>/scripts")
from fetch_learn_materials import discover_courses

cookie = open("/tmp/learn_cookies.json").read().strip()
# discover_courses returns {folder_name: org_unit_id, ...}
courses = discover_courses(cookie)
for folder, ou in courses.items():
    print(f"  {folder:30s}  (ou={ou})")
```

To also show the human-readable course name, fetch it alongside:

```python
import json, sys, requests
sys.path.insert(0, "<skill-dir>/scripts")
from fetch_learn_materials import discover_courses

raw_cookies = json.load(open("/tmp/learn_cookies.json"))
cookie = "; ".join(f"{c['name']}={c['value']}" for c in raw_cookies)
courses = discover_courses(cookie)

# Get names from the API for display
resp = requests.get(
    "https://learn.uwaterloo.ca/d2l/api/lp/1.28/enrollments/myenrollments/",
    params={"orgUnitTypeId": 3},
    headers={"Cookie": cookie},
)
ou_to_name = {
    str(item["OrgUnit"]["Id"]): item["OrgUnit"].get("Name", "")
    for item in resp.json().get("Items", [])
    if "OrgUnit" in item
}
for folder, ou in courses.items():
    print(f"  {folder:30s}  {ou_to_name.get(str(ou), '')}")
```

The `folder` key is exactly what will appear on disk and what `--only` expects.

### Step 2: Classify before showing

**Normal** — folder looks like a standard course code: a subject prefix followed by a number (e.g. `ECE327`, `MATH135`, `CS341`).

**Unusual** — use judgment to flag anything that doesn't look like a real course a student would want to download:
- Has a numeric/hash suffix after an underscore (`ECE318_1277913`) — may be a duplicate section
- Looks like an admin, community, or term org (`Engineering_Co_op_Community`, `WINTER202`, `UW_Resources`)
- Name makes it obvious it's not course material

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

- **Read SYNC_PREFERENCES.md first.** If it exists in the workspace, read it before any other action. Never place files without consulting it.
- **Generate SYNC_PREFERENCES.md on first run.** If it doesn't exist, create it after course discovery and user confirmation — before fetching anything.
- **Never place files under the raw API slug** if SYNC_PREFERENCES.md maps that slug elsewhere. The mapping is authoritative.
- **Ask before placing any unlisted slug.** If a fetched course slug has no entry in SYNC_PREFERENCES.md, stop and ask the user where it goes.
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

## Post-Fetch Placement

After the downloader completes, files sit under `<root>/<API_SLUG>/...`. Use `SYNC_PREFERENCES.md` to move them to the correct destination:

1. For each fetched slug, look up its entry in the mapping table.
2. If the destination folder differs from the API slug folder, move the files:
   ```bash
   # Example: lab content for ECE318_hnafissi_1265 goes into ECE318/Lab Information/
   mv <root>/ECE318_hnafissi_1265/* <root>/ECE318/Lab\ Information/
   rmdir <root>/ECE318_hnafissi_1265  # remove empty slug folder
   ```
3. If the slug folder is the same as the destination (e.g. `ECE327/`), no move needed.
4. If any slug is not in SYNC_PREFERENCES.md, stop and ask the user before placing.

After placement, confirm to the user which files moved where.

---

## Post-Fetch Checks

After every fetch and placement:
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
| Placing files under the raw API slug | Check `SYNC_PREFERENCES.md` first — the mapping is authoritative. API slugs like `ECE318_hnafissi_1265` must be remapped to their destination folders. |
| Skipping SYNC_PREFERENCES.md on first run | If the file doesn't exist, generate it from user input before fetching. Never leave file placement implicit. |

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
