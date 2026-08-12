# IDEAgent OpenCode Instructions

This repository contains IDEAgent, a research-idea generation pipeline.

## Run Requests

When the user asks to run IDEAgent, ideate, generate ideas, do an ideation run, or says a short prompt such as "run ideagent", run the pipeline instead of explaining it.

Use the OpenCode-selected model. Do not add a model name to the IDEAgent command unless the user explicitly asks.

Default real ideation run:

```bash
bash scripts/run_ideagent_from_opencode.sh configs/ideagent_opencode.yaml
```

Quick smoke test, only if the user asks for smoke, quick, test, or plumbing:

```bash
bash scripts/run_ideagent_from_opencode.sh configs/ideagent_opencode_smoke.yaml
```

The helper starts `opencode serve --port 4096` automatically if IDEAgent cannot reach
the OpenCode HTTP server. Do not ask the user to open a second terminal for that common
case.

If a dependency is missing, install the project into the active environment:

```bash
python -m pip install -e .
```

Do not edit source files during a run request. Show the command output and summarize where result files were written.
