# Waterloo Course Tools

Codex plugin containing reusable skills for UWaterloo course workflows.

## Included Skills

- `uwaterloo-learn-download`: syncs course materials from UWaterloo Learn/Brightspace using Learn-only cookies, D2L enrollment discovery, manifest protection, and external material-page candidate discovery.
- `waterloo-piazza-fetch`: uses `browser-use` to join, check, and summarize course Piazza information from a logged-in browser session.

## Repository Layout

```text
waterloo-course-tools/
├── .codex-plugin/
│   └── plugin.json
└── skills/
    ├── uwaterloo-learn-download/
    │   ├── SKILL.md
    │   └── scripts/
    │       └── fetch_learn_materials.py
    └── waterloo-piazza-fetch/
        └── SKILL.md
```

## Privacy Notes

This plugin is designed so private data stays local:

- Do not commit Learn cookies.
- Do not commit downloaded course materials.
- Do not commit Piazza snapshots that contain private course or access information.
- The Learn skill filters exported cookies to `learn.uwaterloo.ca` and its subdomains only.

## Development Checks

Run these before publishing:

```bash
python3 /path/to/plugin-creator/scripts/validate_plugin.py .
python3 -c "import py_compile; py_compile.compile('skills/uwaterloo-learn-download/scripts/fetch_learn_materials.py', cfile='/tmp/fetch_learn_materials.pyc', doraise=True)"
```

Also scan for private or environment-specific content before publishing:

```bash
rg -n "(/Users/|C:\\\\Users\\\\|/home/|learn_cookies|cookies\\.json|door code|password|secret|token)" .
rg -n "\\b[0-9]{7}\\b" skills/
```

Review any matches manually. Seven-digit numbers can be legitimate examples, but they can also be real Learn org-unit IDs or private course identifiers.

Replace placeholder GitHub URLs in `.codex-plugin/plugin.json` before publishing.
