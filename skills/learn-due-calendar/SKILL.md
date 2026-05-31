---
name: learn-due-calendar
description: Use when a user asks to find assignment, homework, HW, deliverable, or course due dates from locally synced UWaterloo Learn materials and add them to Apple Calendar.
---

# Learn Due Dates To Apple Calendar

Use this skill to answer course deadline questions and create Apple Calendar events from locally synced Learn/Brightspace course materials.

## Workflow

1. Identify the course folder the user means. Prefer lecture course folders over lab folders when both exist, and confirm with file names such as course notes, outline, assignments, or announcements.
2. Search local synced materials first:

```bash
rg -n "due|Due|deadline|Assignment|HW|homework|Crowdmark|Deliverable Due" COURSE_DIR learn_content/COURSE_DIR
```

3. For PDFs, extract text instead of guessing from file names:

```bash
pdftotext 'COURSE_DIR/Assignment 2/HW2.pdf' -
pdftotext 'COURSE_DIR/Course Outline/course-outline.pdf' -
```

4. Report due dates with exact absolute dates. If today-relative status matters, compare against the current date.
5. If the user asks to add the deadline to Apple Calendar, create or update an event through Calendar.app with `osascript`.

## Apple Calendar Rules

- Ask only if the course, assignment, or date is ambiguous.
- Use a concise title: `COURSE HWN due` or `COURSE Assignment N due`.
- Include the source in the description, for example: `ECE380 Assignment 2 / HW2 due via Crowdmark.`
- For the user's preferred same-day all-day display, set `allday event` to `true` and set the event start to `00:00:00` and end to `23:59:59` on the same date.
- Keep the returned event id/calendar id if you may need to update the event later in the same conversation.

Example update for a known event:

```bash
osascript \
  -e 'tell application "Calendar"' \
  -e 'set targetEvent to first event of calendar id "CALENDAR_ID" whose uid is "EVENT_UID"' \
  -e 'set start date of targetEvent to date "Wednesday, June 10, 2026 at 12:00:00 AM"' \
  -e 'set end date of targetEvent to date "Wednesday, June 10, 2026 at 11:59:59 PM"' \
  -e 'set allday event of targetEvent to true' \
  -e 'end tell'
```

Example create in the first writable calendar:

```bash
osascript \
  -e 'tell application "Calendar"' \
  -e 'set targetCal to first calendar whose writable is true' \
  -e 'make new event at end of events of targetCal with properties {summary:"ECE380 HW2 due", start date:date "Wednesday, June 10, 2026 at 12:00:00 AM", end date:date "Wednesday, June 10, 2026 at 11:59:59 PM", allday event:true, description:"ECE380 Assignment 2 / HW2 due via Crowdmark."}' \
  -e 'end tell'
```

## Verification

After creating or updating a calendar event, return the title, all-day state, start date, and end date from Calendar.app. Do not claim success from command exit alone.

```bash
osascript \
  -e 'tell application "Calendar"' \
  -e 'return summary of EVENT_REF & " | all-day=" & (allday event of EVENT_REF as string) & " | " & (start date of EVENT_REF as string) & " - " & (end date of EVENT_REF as string)' \
  -e 'end tell'
```
