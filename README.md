# Waterloo Course Tools

Waterloo Course Tools is a small plugin for coding agents that helps Waterloo students keep course information in sync across Learn/Brightspace and Piazza.

It packages reusable skills for downloading Learn materials safely, discovering external course webpages, checking Piazza posts from an authenticated browser session, and turning confirmed Learn due dates into calendar events.

## Quickstart

Give your agent Waterloo Course Tools: [Claude Code](#claude-code), [Codex](#codex).

## How It Works

Waterloo courses often split information across Learn/Brightspace, external course webpages, Piazza, and assignment PDFs. This plugin gives your agent three focused workflows:

1. `uwaterloo-learn-download` discovers the current student's Learn enrollments, downloads course materials through D2L APIs, and protects local edits with a manifest.
2. `waterloo-piazza-fetch` uses `browser-use` with a logged-in browser session to join, check, and summarize Piazza course information.
3. `learn-due-calendar` searches locally synced Learn materials for confirmed due dates and can add them to Apple Calendar on macOS.

The skills are designed to avoid course-specific hardcoding. Learn courses are discovered from the logged-in account, and external material pages are selected from announcement/TOC context rather than fixed hostnames or course names.

## Requirements

- Python 3.
- `browser-use` CLI for Piazza workflows and browser-backed Learn checks.
- `pdftotext` for extracting due dates from PDF course materials.
- macOS Calendar.app access when creating Apple Calendar events.
- A browser session logged in to the relevant UWaterloo Learn/Piazza account.

Install or verify `browser-use` before using the Piazza skill:

```bash
curl -fsSL https://browser-use.com/cli/install.sh | bash
browser-use doctor
```

The Learn downloader script uses Python standard-library HTTP APIs, but it expects valid Learn-only cookies exported from an authenticated browser session.

## Installation

Installation differs by harness. If you use both Claude Code and Codex, install Waterloo Course Tools separately for each one.

### Claude Code

This repository includes a Claude Code marketplace file at `.claude-plugin/marketplace.json`.

Register the marketplace:

```bash
/plugin marketplace add WayneWei228/waterloo-course-tools
```

Install the plugin:

```bash
/plugin install waterloo-course-tools@waterloo-course-tools
```

Validate locally from a clone:

```bash
claude plugin validate .
```

### Codex

This repository includes a Codex plugin manifest at `.codex-plugin/plugin.json`.

Install from the GitHub repository with a Codex marketplace installer:

```bash
npx codex-marketplace add WayneWei228/waterloo-course-tools --plugin
```

If you clone the repository locally for development, validate the plugin with:

```bash
python3 /path/to/plugin-creator/scripts/validate_plugin.py .
```

## The Basic Workflow

1. **Authenticate** - Open the relevant UWaterloo Learn or Piazza account in a browser profile your agent can access.
2. **Export Learn-only cookies** - For Learn syncs, export only cookies scoped to `learn.uwaterloo.ca` or its subdomains.
3. **Sync Learn materials** - Run the bundled Learn downloader against a workspace root. It writes `learn_content/`, mirrors course folders, and protects local edits with `_manifest.json`.
4. **Inspect external material candidates** - When a course links to an external material page, review `learn_content/<COURSE>/_external_candidates.json` and let the agent choose the real material source semantically.
5. **Check Piazza** - Use `browser-use` to inspect joined classes, join a class only after explicit user approval, and write a dated Piazza snapshot.
6. **Find due dates** - Search locally synced Learn materials and extracted PDF text for homework, assignment, deliverable, and course-calendar deadlines.
7. **Add calendar events** - When requested, create or update all-day Apple Calendar events and verify the saved event from Calendar.app.

## What's Inside

### Skills

- **uwaterloo-learn-download** - Downloads UWaterloo Learn/Brightspace course materials, discovers enrollments dynamically, protects local edits with a manifest, and records external webpage candidates.
- **waterloo-piazza-fetch** - Uses `browser-use` to inspect Piazza classes, join requested course Piazza pages, and summarize high-signal course posts.
- **learn-due-calendar** - Finds due dates from locally synced Learn materials and can create verified Apple Calendar events on macOS.

### Scripts

- `skills/uwaterloo-learn-download/scripts/fetch_learn_materials.py` - Stable Learn material fetcher used by the Learn skill.

## Privacy

This plugin is designed so course data stays local:

- Do not commit Learn cookies.
- Do not commit downloaded course materials.
- Do not commit Piazza snapshots that contain private course, access, or personal information.
- Do not commit calendar exports, screenshots, or logs containing private course deadlines.
- The Learn workflow filters exported cookies to `learn.uwaterloo.ca` and its subdomains only.

## Repository Layout

```text
waterloo-course-tools/
├── .claude-plugin/
│   ├── marketplace.json
│   └── plugin.json
├── .codex-plugin/
│   └── plugin.json
├── skills/
│   ├── learn-due-calendar/
│   │   └── SKILL.md
│   ├── uwaterloo-learn-download/
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── fetch_learn_materials.py
│   └── waterloo-piazza-fetch/
│       └── SKILL.md
├── README.md
└── LICENSE
```

## Development Checks

Run these before publishing:

```bash
python3 /path/to/plugin-creator/scripts/validate_plugin.py .
python3 -c "import py_compile; py_compile.compile('skills/uwaterloo-learn-download/scripts/fetch_learn_materials.py', cfile='/tmp/fetch_learn_materials.pyc', doraise=True)"
```

Also scan for sensitive or environment-specific content before publishing:

```bash
rg -n "(/Users/|C:\\\\Users\\\\|/home/|learn_cookies|cookies\\.json|door code|password|secret|token)" .
rg -n "\\b[0-9]{7}\\b" skills/
```

Review any matches manually. Seven-digit numbers can be legitimate examples, but they can also be real Learn org-unit IDs or course-specific identifiers.

## Contributing

This project is early and currently focused on Waterloo Learn/Brightspace and Piazza workflows.

1. Fork or branch the repository.
2. Keep workflows general across Waterloo students and terms.
3. Do not add course-specific hardcoding as the default path.
4. Validate the plugin and skills before opening a PR.

## Updating

Push updates to this repository and update or reinstall the plugin from your agent harness.

For Claude Code:

```bash
/plugin marketplace update waterloo-course-tools
```

For Codex, rerun the repository install command or use your local Codex plugin update flow.

## License

MIT License - see `LICENSE` for details.
