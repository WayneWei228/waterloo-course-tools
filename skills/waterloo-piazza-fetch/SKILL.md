---
name: waterloo-piazza-fetch
description: Use when fetching, joining, checking, or summarizing UWaterloo course Piazza information with browser-use. Covers discovering Piazza links from local Learn/course files, joining classes only when explicitly requested, extracting browser-visible posts/instructor notes/deadlines/unread counts, and writing dated workspace snapshots.
---

# Waterloo Piazza Fetch

Use this skill for Waterloo course Piazza work: checking joined classes, joining a course Piazza after user approval, and summarizing instructor/student Piazza posts into a local Markdown snapshot.

## Core Rules

- Use `browser-use` for Piazza because login/session state and dynamic UI matter.
- Do not join or modify account state unless the user explicitly asks. Reading/opening posts is allowed when the user asks to fetch/check, but warn that unread posts may become read.
- Treat Piazza data as browser-visible unless a stable API archive flow is deliberately added later.
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
browser-use --profile Default open https://piazza.com
browser-use state
```

If `browser-use` cannot access `~/.browser-use` due to sandbox permissions, rerun the browser-use command with approval. Prefer the existing logged-in Default profile when available.

3. For a known course link, open it directly:

```bash
browser-use --profile Default open https://piazza.com/uwaterloo.ca/<term>/<course>
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
