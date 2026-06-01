---
name: learn-grades
description: Use when the user asks to check, view, or fetch their grades on UWaterloo Learn/Brightspace for any or all enrolled courses.
---

# UWaterloo Learn Grades

## Overview

Fetch grades by scraping the HTML grades page directly with Learn cookies. **Do not use the D2L REST API (`myGradeValues`) as the primary source** — it silently returns empty arrays for courses that DO have visible grades. The HTML page at `main.d2l?ou=<ou>` is authoritative.

## Workflow

### Step 1 — Load cookies

```python
import json, urllib.request, re

raw = json.load(open("/tmp/learn_cookies.json"))
cookie = "; ".join(f"{c['name']}={c['value']}" for c in raw)
headers = {"Cookie": cookie, "User-Agent": "Mozilla/5.0"}
```

If `/tmp/learn_cookies.json` is missing, use the `uwaterloo-learn-download` skill to authenticate and export cookies first.

### Step 2 — Discover course org unit IDs

```python
import sys
sys.path.insert(0, "/path/to/skills/uwaterloo-learn-download/scripts")
from fetch_learn_materials import discover_courses

courses = discover_courses(cookie)  # {folder_name: org_unit_id}
```

Skip admin orgs (`Engineering_Co_op_Community`, `WINTER202`, `UW_Resources`). Keep standard course slugs (`CS341`, `STAT230`, `ECE327`, etc.). Duplicates appear as `DEPT123_<ou>` — these are the same course from a different section org; skip them and use the primary slug only.

### Step 3 — Fetch HTML grades page for each course

```python
def fetch_grades(ou, cookie):
    url = f"https://learn.uwaterloo.ca/d2l/lms/grades/my_grades/main.d2l?ou={ou}"
    req = urllib.request.Request(url, headers={"Cookie": cookie, "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        html = r.read().decode(errors="replace")

    table = re.search(r'<table[^>]*>(.*?)</table>', html, re.DOTALL)
    if not table:
        return []

    results = []
    for row in re.findall(r'<tr[^>]*>(.*?)</tr>', table.group(1), re.DOTALL):
        label = re.search(r'<label>(.*?)</label>', row)
        if not label:
            continue
        name = html.unescape(label.group(1).strip())
        spans = re.findall(r'<span[^>]*>([^<]+)</span>', row)
        score = next((s.strip() for s in spans
                      if re.match(r'[\d.]+ / [\d.]+', s.strip()) or s.strip() == '--'), "")
        is_child = 'd_g_treeNodeImage' in row
        results.append(("  " if is_child else "", name, score))
    return results
```

### Step 4 — Handle expired cookies

If the fetched HTML contains `"login"` or `"Sign in"` near the top, cookies are expired. Re-authenticate using `uwaterloo-learn-download` skill, then retry.

```python
if "sign in" in html[:500].lower() or "login" in html[:500].lower():
    print("Cookies expired — re-authenticate first.")
```

## Reading the Output

| Pattern | Meaning |
|---------|---------|
| `item: 95.83 / 100` | Grade released |
| `item: 0 / 30` (no %) | Grade item exists but not yet released |
| No rows in table | Instructor hasn't set up gradebook yet |

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Using `myGradeValues` REST API as primary | API returns `[]` for most courses even when grades are visible — always use HTML page |
| Concluding "no grades" from empty API response | Re-fetch via HTML; API and HTML frequently disagree |
| Concluding "no grades" when HTML shows all zeros | Zeros mean items exist but unreleased, not that gradebook is empty |
| Using browser-use to fetch grades | Not needed — cookies work directly; browser-use forces Duo re-auth every session |
| Hardcoding org unit IDs | Use `discover_courses()` to discover dynamically |
