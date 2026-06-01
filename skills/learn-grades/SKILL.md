---
name: learn-grades
description: Use when the user asks to check, fetch, or show their grades on UWaterloo Learn/Brightspace across any or all enrolled courses.
---

# UWaterloo Learn Grades

## Overview

Fetches grades from UWaterloo Learn using a `browser-use` headed session. The HTML grades page at `main.d2l?ou=<ou>` is the authoritative source — the D2L REST API (`myGradeValues`) returns empty arrays for many courses even when grades are clearly visible in the browser.

**Do NOT use the REST API as the primary source.** Always use the HTML grades page via browser-use.

## Workflow

### Step 1 — Check for existing Learn cookies

```bash
ls /tmp/learn_cookies.json 2>/dev/null && echo "found" || echo "missing"
```

If missing, use the `uwaterloo-learn-download` skill's authentication step first.

If present but you get HTTP errors when discovering courses (Step 2), cookies are likely expired — re-authenticate before continuing.

### Step 2 — Discover enrolled courses

```python
import json, sys
sys.path.insert(0, "/path/to/waterloo-course-tools/skills/uwaterloo-learn-download/scripts")
from fetch_learn_materials import discover_courses

raw = json.load(open("/tmp/learn_cookies.json"))
cookie = "; ".join(f"{c['name']}={c['value']}" for c in raw)
courses = discover_courses(cookie)  # {folder_name: org_unit_id}
for folder, ou in courses.items():
    print(f"{folder:35s}  ou={ou}")
```

Replace `/path/to/waterloo-course-tools` with the actual plugin cache path, e.g.:
`/Users/<user>/.claude/plugins/cache/waterloo-course-tools/waterloo-course-tools/<version>`

Keep normal course slugs (`ECE327`, `MATH135`) and skip admin orgs (`Engineering_Co_op_Community`, `WINTER202`, `UW_Resources`).

If `discover_courses` raises an exception or returns HTTP 401/403, the cookies are expired — stop and re-authenticate.

### Step 3 — Check for active browser-use session

```bash
browser-use sessions
```

- **Session already active** → go to Step 4 directly using `browser-use open` (no `--headed`)
- **No active session** → detect Chrome profile and open a new headed session:

```bash
browser-use profile list
browser-use --headed --profile "<detected profile>" open \
  "https://learn.uwaterloo.ca/d2l/lms/grades/my_grades/main.d2l?ou=<FIRST_OU>"
browser-use state
```

**Duo MFA:** If `browser-use state` shows a Duo prompt instead of a grades table, tell the user: *"Please approve the Duo push on your phone."* Wait for their confirmation, then run `browser-use state` again. Continue only when state shows a grades table (contains "Grade Item" and "Points" headers).

### Step 4 — Read grades for each course

For the first course (already open from Step 3), call `browser-use state` and parse the output (see **Reading the Output** below).

For each remaining course, navigate within the existing session:

```bash
browser-use open "https://learn.uwaterloo.ca/d2l/lms/grades/my_grades/main.d2l?ou=<OU>"
browser-use state
```

If state doesn't show a grades table (no "Grade Item" header), wait 2 seconds and try `browser-use state` once more. If it still doesn't show a grades table, note that course as "page did not load" and continue to the next.

### Step 5 — Cleanup

```bash
browser-use close
browser-use sessions
# Expected: No active sessions
```

## Reading the Output

**Released grade item** (has a percentage line):
```
Lab 1
    99.5 / 100
    1.00 / 1
    99.5 %
```

**Unreleased grade item** (no percentage):
```
Quiz 1
    0 / 30
    0 / 15
```

**Category / aggregate row:**
```
Laboratory
    19.9 / 20
    99.5 %
```

**Course with no grades configured yet** — state output will show "Grade Item / Points / Weight Achieved" header but no rows beneath it.

**Page did not load** — state output will show navigation elements and no grade table header at all.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Using `myGradeValues` REST API as primary source | API returns `[]` for most courses; use the HTML grades page via browser-use |
| Concluding "no grades released" from an empty API response | Re-check via browser-use — API and HTML frequently disagree |
| Hardcoding org unit IDs | Use `discover_courses()` to discover them dynamically |
| Opening `--headed` session when one is already running | Run `browser-use sessions` first; if active, use `browser-use open` not `--headed open` |
| Leaving session open after fetching | Always run `browser-use close` + verify no active sessions |
| Continuing after Duo prompt without confirming | Wait for user to approve Duo push, then verify state shows grades table |
| Treating expired cookies as missing cookies | Expired cookies are present but cause API errors — re-auth, don't just skip |
