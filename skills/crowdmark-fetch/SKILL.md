---
name: crowdmark-fetch
description: Use when the user asks to check Crowdmark assignments, grades, scores, due dates, submission status, or assignment content from app.crowdmark.com. Requires browser-use CLI.
---

# Crowdmark Fetch

## Overview

Retrieve student assignment data from Crowdmark (app.crowdmark.com) using `browser-use` with an existing Chrome profile. Covers: assignment list, due dates, submission status, grades/scores per question, and assignment content.

UWaterloo Crowdmark accounts sign in through WatIAM SSO + Duo. **Always use a headed Chrome profile** to reuse an existing authenticated session — never try to enter credentials or automate SSO.

## Requirements

- `browser-use` CLI installed and working (`browser-use doctor`)
- Chrome logged in to Crowdmark via WatIAM SSO

## Workflow

### Step 1 — Detect Chrome profile

```bash
browser-use profile list
```

Pick the profile the user normally uses. Do not hardcode a profile name.

### Step 2 — Open Crowdmark student dashboard

```bash
browser-use --headed --profile "<detected profile>" open https://app.crowdmark.com/student
browser-use state
```

Read the state output. If it shows a "Sign in" or WatIAM login page, the user must complete SSO in the headed window:

```
The Crowdmark page is showing a sign-in screen. Please complete the WatIAM login
and Duo authentication in the Chrome window. Tell me when you're done.
```

Wait for confirmation, then re-run `browser-use state`. Continue only when state shows the student dashboard (course cards or assignment list).

### Step 3 — Enumerate assignments

From the dashboard, check what's visible in state. Crowdmark's student view shows:

- Course cards → click into each course to see its assignments
- Or a unified assignment list (if the dashboard shows all courses at once)

**Always use `browser-use state` to discover element indices.** Never guess selectors. Example flow:

```bash
browser-use state
# Read indices of course cards from the output, then:
browser-use click <course-card-index>
browser-use state
# Read assignment rows
```

For each assignment visible in state, collect:
- Assignment name
- Due date (if shown)
- Submission status (Submitted / Not Submitted / Late)
- Score (if released — e.g. "18 / 25")

If assignments are paginated or collapsed, scroll and re-check state:

```bash
browser-use scroll down
browser-use state
```

### Step 4 — Get per-question grade breakdown (if needed)

Click into a graded assignment to see the score per question:

```bash
browser-use click <assignment-row-index>
browser-use state
```

The detail page typically shows a question-by-question breakdown. Collect:
- Total score
- Score per question/part
- Any written feedback from the marker

If the assignment has a PDF view ("View your submission" or similar button), identify its index in state and click it only if the user explicitly asked for assignment content.

### Step 5 — Export session cookies (optional, for repeat use)

If the user wants to avoid re-authenticating on future runs, export and filter Crowdmark cookies:

```bash
browser-use cookies export --url https://app.crowdmark.com /tmp/crowdmark_cookies_raw.json
```

```python
import json

raw = json.load(open("/tmp/crowdmark_cookies_raw.json"))
cookies = [
    c for c in raw
    if c.get("domain", "").endswith("crowdmark.com")
]
json.dump(cookies, open("/tmp/crowdmark_cookies.json", "w"), indent=2)
```

Store at `/tmp/crowdmark_cookies.json`. Never commit this file. These cookies expire — re-export after a new SSO session if you get 401/redirect errors.

### Step 6 — Cleanup

```bash
browser-use close
browser-use sessions
```

Expected output: `No active sessions`. Do not leave a headed Chrome window running.

---

## Output Format

Summarize results in a table per course:

```
CS 341 — Algorithms
  Assignment 1     Due: Jan 15 2026   Status: Submitted   Score: 18 / 25
  Midterm          Due: Feb 10 2026   Status: Submitted   Score: 72 / 100
  Assignment 2     Due: Mar 1 2026    Status: Not submitted

ECE 327 — Digital Hardware Systems
  Lab 1            Due: Jan 22 2026   Status: Submitted   Score: —  (not yet released)
  Assignment 1     Due: Feb 5 2026    Status: Submitted   Score: 14 / 20
```

Show `—` for scores not yet released. Show `Not submitted` for items with no submission.

For question-level breakdowns:

```
CS 341 — Assignment 1 (18 / 25)
  Q1a: 5 / 5
  Q1b: 3 / 5
  Q2:  10 / 15
  Feedback: "Good approach on Q2 but missing the base case proof."
```

---

## Hard Rules

- **Always use `--headed --profile`** — Crowdmark requires WatIAM SSO; headless mode will hit the login page with no way to authenticate.
- **Always run `browser-use state` before clicking** — never guess element indices; they change per page.
- **Do not automate credentials** — SSO requires Duo MFA. Always ask the user to complete login in the headed window if needed.
- **Always close browser-use when done** — run `browser-use close` + verify no active sessions.
- **Never commit cookies** — `/tmp/crowdmark_cookies.json` is ephemeral; remind the user not to commit it.
- **Do not open assignment PDFs unless asked** — opening a submission for viewing is fine for grade/feedback; downloading or bulk-opening PDFs requires explicit user request.

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Using `browser-use navigate`, `fill`, `get-text` commands | These don't exist. Use `open`, `state`, `click <index>`, `input <index> "text"` |
| Using CSS selectors to click elements | browser-use uses numeric indices from `state` output, not selectors |
| Opening in headless mode | WatIAM SSO requires a visible window; always use `--headed --profile` |
| Trying to fill in username/password | UWaterloo Crowdmark uses SSO + Duo — have the user log in manually in the headed window |
| Forgetting `browser-use close` at the end | Always close; leaving a headed session running blocks the user from closing Chrome |
| Assuming selectors like `.grade`, `.course-list` | Run `browser-use state` to see real element indices; the UI is a React SPA and class names are generated |
| Using browser-use just to get cookies and then switching to raw HTTP | Crowdmark's session cookies are complex; use browser-use state navigation throughout |
