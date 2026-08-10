# IDEAgent Gemini Setup Changes

This file documents the exact local changes made while getting IDEAgent running with a Gemini API key.

The upstream repository was cloned from:

```bash
git clone https://github.com/declare-lab/IDEAgent.git
```

The local setup used:

```bash
cd IDEAgent
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

The default upstream command initially did not run in this environment because it required `OPENAI_API_KEY`:

```bash
.venv/bin/python scripts/run_ideagent.py --config configs/ideagent.yaml
```

It failed with:

```text
ValueError: OpenAI API key not found. Set the 'OPENAI_API_KEY' environment variable or add it to a .env file.
```

The goal of these changes was to make a small Gemini-only path that is easy to run from the terminal without exposing the API key in shell history.

## 1. Source Bug Fix

Changed file:

```text
ideagent/generation_loop.py
```

Added one field to the `Config` dataclass:

```python
feasibility_prompt_mode: str = "generic"
```

Why this was needed:

`scripts/run_ideagent.py` already passes this keyword argument when constructing `Config`:

```python
feasibility_prompt_mode=str(run.get("feasibility_prompt_mode", "generic")),
```

But the `Config` dataclass in `ideagent/generation_loop.py` did not define the field. That caused this crash:

```text
TypeError: Config.__init__() got an unexpected keyword argument 'feasibility_prompt_mode'
```

This is a compatibility fix between the existing runner and the existing dataclass. It does not change the search behavior by itself; it only lets the runner construct the config object successfully.

## 2. Gemini Secret Setup Script

Added file:

```text
scripts/set_gemini_secret.sh
```

What it does:

- Prompts for the Gemini API key using hidden terminal input.
- Removes a trailing carriage return if one is pasted.
- Rejects empty input.
- Writes a local secret file at:

```text
.env.gemini.secret
```

- Stores the key as:

```text
GEMINI_API_KEY_B64=<base64 value>
```

- Sets file permissions to `600`.

Command:

```bash
./scripts/set_gemini_secret.sh
```

Important note:

Base64 is not encryption. This keeps the key out of shell history and casual plaintext views, but it is still a local secret file. The file is ignored by git because the upstream `.gitignore` already ignores `.env.*`.

## 3. Gemini Run Wrapper

Added file:

```text
scripts/run_with_gemini_secret.sh
```

What it does:

- Uses an already exported `GEMINI_API_KEY` if present.
- Otherwise reads `.env.gemini.secret`, base64-decodes `GEMINI_API_KEY_B64`, and exports `GEMINI_API_KEY` only for the child IDEAgent process.
- Defaults to the synthetic smoke config:

```text
configs/ideagent_gemini_smoke.yaml
```

- Lets the caller pass a different config as the first argument.
- Supports re-entering/replacing the stored key with:

```bash
./scripts/run_with_gemini_secret.sh --set-key
```

Default run command:

```bash
./scripts/run_with_gemini_secret.sh
```

Real one-topic run command:

```bash
./scripts/run_with_gemini_secret.sh configs/ideagent_gemini_one_topic.yaml
```

## 4. Synthetic Gemini Smoke Config

Added file:

```text
configs/ideagent_gemini_smoke.yaml
```

Purpose:

This is the default safe smoke test. It uses a synthetic toy topic instead of the bundled real paper corpus, so the first live API test can verify Gemini/client/parser/output plumbing without sending real corpus content to the external API.

Key settings:

```yaml
data:
  input_jsonl: data/gemini_smoke_topic.jsonl
  output_dir: results/gemini-smoke
```

All roles use Gemini:

```yaml
ideator: gemini-3.6-flash
critic: gemini-3.6-flash
quality: gemini-3.6-flash
steno: gemini-3.6-flash
judge: gemini-3.6-flash
```

The run is intentionally tiny:

```yaml
max_budget: 1
soundness_n: 1
accepted_refinement_limit: 0
auxiliary_attempt_limit: 0
novelty_branch_limit: 0
```

That means:

- One independent generated idea.
- One soundness vote.
- No repair draft.
- No accepted-polish draft.
- No novelty branch.

This keeps the smoke run cheap and fast.

## 5. Synthetic Smoke Topic

Added file:

```text
data/gemini_smoke_topic.jsonl
```

Purpose:

This is fake toy data that satisfies IDEAgent's input schema. It is only for API smoke testing.

It contains:

- One synthetic `topic_id`: `smoke-001`.
- One synthetic background paper.
- One synthetic target paper.

It does not contain real paper content.

## 6. Real One-Topic Gemini Config

Added file:

```text
configs/ideagent_gemini_one_topic.yaml
```

Purpose:

This config runs IDEAgent on the real bundled corpus, but still as a minimal test:

```yaml
data:
  input_jsonl: data/bkgd_papers.jsonl
  output_dir: results/gemini-one-topic
```

It uses only the first topic:

```yaml
init_topic_idx: 0
end_topic_idx: 1
```

It keeps the run tiny:

```yaml
max_budget: 1
soundness_n: 1
accepted_refinement_limit: 0
auxiliary_attempt_limit: 0
novelty_branch_limit: 0
```

All agent roles use:

```yaml
model_id: gemini-3.6-flash
api_key_env: GEMINI_API_KEY
```

This config sends the first bundled paper topic from `data/bkgd_papers.jsonl` to Gemini.

## 7. Local Generated Files

The setup also created local files/directories that are not meant to be committed:

```text
.venv/
.env.gemini.secret
results/gemini-smoke/
results/gemini-one-topic/
```

What they are:

- `.venv/`: local Python virtual environment.
- `.env.gemini.secret`: local encoded Gemini key file.
- `results/gemini-smoke/`: output from the synthetic smoke run.
- `results/gemini-one-topic/`: output from the real one-topic run.

The upstream `.gitignore` already excludes `.venv/`, `.env.*`, and `/results/`.

## 8. Validation Performed

Dependency install:

```bash
.venv/bin/python -m pip install -e .
```

Import and compile checks:

```bash
.venv/bin/python -m compileall -q ideagent scripts
.venv/bin/python -c 'import ideagent; import ideagent.clients; import ideagent.generation_loop; print("import ok")'
```

Config construction check:

```bash
.venv/bin/python - <<'PY'
from ideagent.generation_loop import Config
Config(input_jsonl='data/bkgd_papers.jsonl', output_dir='results/test', feasibility_prompt_mode='generic')
print('Config accepts feasibility_prompt_mode')
PY
```

Synthetic smoke run:

```bash
./scripts/run_with_gemini_secret.sh
```

Observed successful synthetic result:

```text
[g001] free          nb= 80 cl= 75 snd= 77.8 div=100 -> accepted
ACTIVE=1 DISC=1 (repair=0)
Done. 1 topic(s). Output dir: results/gemini-smoke
```

Real one-topic run:

```bash
./scripts/run_with_gemini_secret.sh configs/ideagent_gemini_one_topic.yaml
```

Observed successful real run completion:

```text
[g001] free          nb= 80 cl= 85 snd= 33.3 div=100 -> reject_unsound
ACTIVE=0 DISC=0 (repair=0)
Done. 1 topic(s). Output dir: results/gemini-one-topic
```

This was a real negative result, not a runtime failure. IDEAgent generated an idea, extracted a signature, ran quality/soundness evaluation, judged diversity, wrote artifacts, and rejected the idea because the soundness score failed the gate.

## 9. How To Reproduce

From a fresh checkout:

```bash
git clone <this-repo-url>
cd IDEAgent
python3 -m venv .venv
.venv/bin/python -m pip install -e .
./scripts/run_with_gemini_secret.sh --set-key
./scripts/run_with_gemini_secret.sh
```

To run the real one-topic Gemini test:

```bash
./scripts/run_with_gemini_secret.sh configs/ideagent_gemini_one_topic.yaml
```

To replace the stored key:

```bash
./scripts/run_with_gemini_secret.sh --set-key
```

To use an environment variable instead of the local encoded secret file:

```bash
export GEMINI_API_KEY="your-key"
./scripts/run_with_gemini_secret.sh
```

