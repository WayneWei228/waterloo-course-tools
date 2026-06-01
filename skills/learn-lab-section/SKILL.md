---
name: learn-lab-section
description: Use when the user asks about their lab section, lecture section, tutorial section, or course section number on UWaterloo Learn.
---

# UWaterloo Learn Lab/Section Lookup

## Overview

Fetch all enrolled sections (LAB, LEC, TUT) directly from the D2L enrollment API using `orgUnitTypeId=4` (Groups). This is more reliable and faster than scraping the `user_group_list.d2l` HTML page — one paginated API call returns all section codes for all courses at once.

Section codes follow the format: `<term>-<DEPT>.<NUM>.<section>.<seq>.<type>`
Example: `1265-ECE.380.206.1.LAB` → ECE380, Lab section 206, Spring 2026

## Workflow

### Step 1 — Load cookies

```python
import json, urllib.request

raw = json.load(open("/tmp/learn_cookies.json"))
cookie = "; ".join(f"{c['name']}={c['value']}" for c in raw)
headers = {"Cookie": cookie, "Accept": "application/json"}
```

If `/tmp/learn_cookies.json` is missing or expired (HTTP 401/403), use the `uwaterloo-learn-download` skill to re-authenticate first.

### Step 2 — Fetch all group enrollments (orgUnitTypeId=4)

```python
def fetch_all_sections(cookie):
    sections = []
    bookmark = ""
    while True:
        url = (f"https://learn.uwaterloo.ca/d2l/api/lp/1.28/enrollments/myenrollments/"
               f"?orgUnitTypeId=4&pageSize=100{('&bookmark=' + bookmark) if bookmark else ''}")
        req = urllib.request.Request(url, headers={"Cookie": cookie, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        for item in data.get("Items", []):
            name = item.get("OrgUnit", {}).get("Name", "")
            sections.append(name)
        bookmark = data.get("PagingInfo", {}).get("Bookmark", "")
        if not data.get("PagingInfo", {}).get("HasMoreItems"):
            break
    return sections
```

### Step 3 — Parse and display sections

```python
import re

def parse_section(name):
    # Handles: 1265-ECE.380.206.1.LAB  1265-MATH.135.081.1.LEC
    m = re.match(r'(\d+)-([A-Z]+)\.(\d+[A-Z]*)\.(\d+)\.(\d+)\.(LAB|LEC|TUT|SEM|PRJ|TST)', name)
    if m:
        term, dept, num, section, seq, stype = m.groups()
        return {"term": term, "course": f"{dept}{num}", "section": section, "type": stype, "raw": name}
    return None

sections = fetch_all_sections(cookie)
parsed = [parse_section(s) for s in sections]
parsed = [p for p in parsed if p]  # drop non-matching (admin groups, etc.)

# Filter to current term (highest term code = most recent)
current_term = max(p["term"] for p in parsed)
parsed = [p for p in parsed if p["term"] == current_term]

# Dedup: API can return the same section multiple times
seen = set()
deduped = []
for p in parsed:
    key = (p["course"], p["type"], p["section"])
    if key not in seen:
        seen.add(key)
        deduped.append(p)

# Group by course
from collections import defaultdict
by_course = defaultdict(list)
for p in deduped:
    by_course[p["course"]].append(p)

for course, entries in sorted(by_course.items()):
    labs = [e for e in entries if e["type"] == "LAB"]
    lecs = [e for e in entries if e["type"] == "LEC"]
    tuts = [e for e in entries if e["type"] == "TUT"]
    print(f"{course}: LAB {labs[0]['section'] if labs else '—'}  "
          f"LEC {lecs[0]['section'] if lecs else '—'}  "
          f"TUT {tuts[0]['section'] if tuts else '—'}")
```

## Output Format

```
ECE318: LAB 206  LEC 002  TUT 102
ECE327: LAB 203  LEC 001  TUT 101
ECE350: LAB 203  LEC 001  TUT 101
ECE380: LAB 206  LEC 002  TUT 102
MATH135: LAB —   LEC 081  TUT —
PSYCH207: LAB —  LEC 081  TUT —
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Scraping `user_group_list.d2l` HTML per course | Use `orgUnitTypeId=4` API — one call gets all courses at once |
| Using `orgUnitTypeId=3` (Course Offerings) | Type 3 gives course OUs but no section codes; use type 4 for sections |
| Using browser-use to open group pages | Not needed — cookies work directly; browser-use forces Duo re-auth every session |
| Assuming all courses have a LAB section | Online courses (PSYCH207, MATH135) only have LEC; filter by type before displaying |
| Forgetting to paginate | API returns 100 items per page; loop until `HasMoreItems` is false |
