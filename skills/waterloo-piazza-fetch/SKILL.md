---
name: waterloo-piazza-fetch
description: Use when fetching, joining, checking, or summarizing UWaterloo course Piazza information with browser-use. Covers discovering Piazza links from local Learn/course files, joining classes only when explicitly requested, extracting browser-visible posts/instructor notes/deadlines/unread counts, and writing dated workspace snapshots.
---

# Waterloo Piazza Fetch

Use this skill for Waterloo course Piazza work: checking joined classes, joining a course Piazza after user approval, and summarizing instructor/student Piazza posts into a local Markdown snapshot.

## Requirements

- `browser-use` CLI must be installed and working.
- The local Chrome profile used by `browser-use` must be logged in to Piazza.
- If `browser-use` is missing, install it before continuing:

```bash
curl -fsSL https://browser-use.com/cli/install.sh | bash
browser-use doctor
```

## Core Rules

- Use `browser-use` for Piazza because login/session state and dynamic UI matter.
- Prefer headed local Chrome profile sessions for authenticated work:
  `browser-use --headed --profile "<detected Chrome profile>" open https://piazza.com`.
- Do not join or modify account state unless the user explicitly asks. Reading/opening posts is allowed when the user asks to fetch/check, but warn that unread posts may become read.
- For specific user questions, prefer targeted authenticated API queries over full snapshots or opening many unread posts.
- Do not hardcode this user's current courses as the general solution. Discover course links from local files and Piazza class dropdown state.
- Keep sensitive access info private to the user's local workspace; do not paste door codes or private post details into public messages unless the user asks.

## Standard Workflow

1. Inspect local course files for Piazza links:

```bash
rg -n "piazza|Piazza|piazza.com" . -S
find . -maxdepth 4 -iname '*piazza*' -print
```

2. Check browser-use state:

```bash
browser-use sessions
browser-use profile list
browser-use --headed --profile "<detected Chrome profile>" open https://piazza.com
browser-use state
```

If `browser-use` cannot access `~/.browser-use` due to sandbox permissions, rerun the browser-use command with approval. Use headed mode so the user can see and complete login in the correct local Chrome window. Do not hardcode a profile name; use the profile name returned by `browser-use profile list`.

3. For a known course link, open it directly:

```bash
browser-use --headed --profile "<detected Chrome profile>" open https://piazza.com/uwaterloo.ca/<term>/<course>
browser-use state
```

4. If the course is not joined:

- Report that it exists and is not joined.
- Join only after explicit user confirmation.
- To join, click the `Student` radio/input, then click `Join Classes`.
- Verify the page lands in the class Q&A feed and the class dropdown shows the course.

5. For joined classes, use `browser-use state` on the Q&A page and capture:

- Piazza class name and course context.
- Total posts, unread posts, unanswered questions/followups, instructor response count, enrolled count when visible.
- Pinned notes, instructor notes, deadline/weighting/logistics posts, and recent high-signal Q&A.
- Not-joined course links and what action is needed.

Open individual posts only when needed for full details:

```bash
browser-use click <post-wrapper-index>
browser-use state
```

## Targeted Piazza API Query

When the user asks a specific question, such as "Does ECE327 have anyone looking for a lab teammate?", do not default to a full archive. Use the logged-in browser session to query only relevant posts:

1. Open the course in headed local Chrome and get the class id from the URL:

```bash
browser-use --headed --profile "<detected Chrome profile>" open https://piazza.com
browser-use state
browser-use tab list
```

2. Export Piazza cookies from the authenticated session:

```bash
browser-use cookies export --url https://piazza.com /tmp/piazza_cookies.json
```

3. Use Piazza's authenticated API for the selected class:

```text
POST https://piazza.com/logic/api?method=network.filter_feed
{"method":"network.filter_feed","params":{"nid":"<class_id>","sort":"date_desc","hidden":"both"}}

POST https://piazza.com/logic/api?method=content.get
{"method":"content.get","params":{"cid":"<post_id>"}}
```

Include the `session_id` cookie value as the `CSRF-Token` header when making local HTTP requests. First call `network.filter_feed`, filter post subjects/snippets by the user's keywords, then call `content.get` only for the matching post ids.

For teammate/lab-partner questions, search terms should include:

```text
lab partner, teammate, team mate, group, section swap, swap lab, lab section, partner
```

Always include references in the answer so the user can double-check:

```text
https://piazza.com/class/<class_id>/post/<post_nr>
```

Use `post_nr` from the API field `nr`, not the opaque post id.

## Output

Write a dated Markdown snapshot in the active workspace, for example:

```text
Piazza_Information_YYYY-MM-DD.md
```

Recommended sections:

- `Joined Classes Found`
- `Not Joined / Needs Action`
- `Important Items`
- one subsection per course
- `Notes`

Mention in the snapshot:

- Fetch date.
- That it was fetched through `browser-use`.
- That opening unread posts may mark them as read.
- Whether it is a browser-visible snapshot rather than a full API archive.

## Useful Signals

Prioritize:

- Instructor notes.
- Pinned notes.
- Due dates and grading weights.
- Lab room/access/process information.
- Course logistics and lecture/tutorial changes.
- Posts with instructor answers that clarify assignments, labs, exams, or grading.

Deprioritize:

- Generic `Welcome to Piazza!` posts.
- Piazza Careers/profile prompts.
- Teammate-search posts unless the user asks for group/project information.
- Long student-only technical Q&A unless it directly affects a current assignment/lab.

## Example Join Pattern

When the user asks to join a course and the page shows:

- the expected course title
- `Join as: Student`
- `Join Classes`

Then:

```bash
browser-use click <student-radio-index>
browser-use click <join-classes-button-index>
browser-use state
```

Confirm success only after the state shows the Q&A feed with class selection set to the requested course.
