---
description: Shortcut for the IDEAgent ideation run
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
bash scripts/run_ideagent_from_opencode.sh <CONFIG>
```

The helper starts `opencode serve --port 4096` automatically if it is not already
running. Keep the shell output visible in OpenCode. When it finishes, report the output
directory and the final idea JSONL file.
