---
description: Run IDEAgent ideation with the currently selected OpenCode model
agent: build
---

Run IDEAgent now. Do not edit files.

Use the model already selected in OpenCode. Do not override the model.

Arguments from the user, if any: $ARGUMENTS

Choose the config this way:

- If the arguments mention smoke, quick, test, or plumbing, use `configs/ideagent_opencode_smoke.yaml`.
- If the arguments contain a path ending in `.yaml` or `.yml`, use that path.
- Otherwise use `configs/ideagent_opencode.yaml`.

Run this as a shell command from the repository root, replacing `<CONFIG>` with the chosen config:

```bash
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; elif command -v python3.12 >/dev/null 2>&1; then PY=python3.12; elif command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
IDEAGENT_LIVE_PROGRESS=1 PYTHONUNBUFFERED=1 "$PY" -u scripts/run_ideagent.py --config <CONFIG>
```

Keep the shell output visible in OpenCode. When it finishes, report the output directory and the final idea JSONL file.

