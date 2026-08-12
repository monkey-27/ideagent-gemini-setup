# IDEAgent OpenCode Instructions

This repository contains IDEAgent, a research-idea generation pipeline.

## Run Requests

When the user asks to run IDEAgent, ideate, generate ideas, do an ideation run, or says a short prompt such as "run ideagent", run the pipeline instead of explaining it.

Use the OpenCode-selected model. Do not add a model name to the IDEAgent command unless the user explicitly asks.

Default real ideation run:

```bash
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; elif command -v python3.12 >/dev/null 2>&1; then PY=python3.12; elif command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
IDEAGENT_LIVE_PROGRESS=1 PYTHONUNBUFFERED=1 "$PY" -u scripts/run_ideagent.py --config configs/ideagent_opencode.yaml
```

Quick smoke test, only if the user asks for smoke, quick, test, or plumbing:

```bash
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; elif command -v python3.12 >/dev/null 2>&1; then PY=python3.12; elif command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
IDEAGENT_LIVE_PROGRESS=1 PYTHONUNBUFFERED=1 "$PY" -u scripts/run_ideagent.py --config configs/ideagent_opencode_smoke.yaml
```

If a dependency is missing, install the project into the active environment:

```bash
python -m pip install -e .
```

Do not edit source files during a run request. Show the command output and summarize where result files were written.

