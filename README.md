# ?? IDEAgent

**Agentic Quality-Diversity Search for Research Idea Generation**

An agentic quality-diversity (QD) search system for generating research ideas,
plus baseline generation methods used for comparison.

## ?? Abstract

> Large Language Models (LLMs) have significantly automated the process of scientific
> discovery over the past few years. However, existing systems share one core limitation:
> they generate and optimize ideas independently for either Quality or Diversity. This
> often leads to the generation of ideas in close proximity to one another or to a large
> set of trivial, unsound, or unclear concepts. In this work, we instead argue that
> research ideation should be treated as a conjunction of both objectives and framed as a
> Quality-Diversity (QD) search. In line with this perspective, we introduce IDEAgent, a
> multi-agent framework that manages the evolution of ideas through lineages. We jointly
> drive Quality using multi-objective feedback for dedicated repair and refinement, while
> Diversity is achieved through lightweight sequential memory and explicit comparison
> against completed ideas, their historical ancestors, and rejected proposals. To
> systematically evaluate this QD conjunction, we develop Yield, a joint metric that
> computes the largest set of mutually diverse ideas that satisfy a predetermined quality
> threshold. Finally, through evaluations across 32 topics spanning 8 domains of Computer
> Science, we show that IDEAgent outperforms the best baseline by 3.89x on Yield, while
> achieving non-zero Yield on 8x more topics. We further corroborate these findings
> through an analysis of quality improvements, showing that repair and refinement are
> crucial for building logical rigor and clarity while preserving non-obviousness.

## ??? What Is Here

```text
.
??? ideagent/          # runtime package: IDEAgent's search/repair/refinement
?                      # loop, quality + diversity evaluators, shared infra
??? baselines/
?   ??? simple/        # stateless-independent, single-shot batch, and
?   ?                  # sequential-memory baselines
?   ??? nova/          # NOVA-style closed-book baseline
??? scripts/           # runners and evaluators (run_ideagent.py,
?                      # eval_ideas.py, select_lineage_representatives.py)
??? configs/           # canonical YAML configs for each pipeline
??? data/
    ??? bkgd_papers.jsonl  # topic input data
    ??? examples/          # sample generations from IDEAgent and every baseline
```

## ?? Setup

```bash
pip install -e .
```

Set the relevant API keys as environment variables or in a `.env` file
(`OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY` ? see `ideagent/clients.py`).

### OpenCode backend

Recommended OpenCode-native flow:

```bash
opencode
```

Pick your model from OpenCode's model dropdown, then type:

```text
run ideagent
```

or use the project command:

```text
/ideagent
```

OpenCode reads `AGENTS.md` and the project command in `.opencode/commands/`, then runs
IDEAgent through its shell tool using the model selected in OpenCode. The default is a
real one-topic ideation run:

```bash
python scripts/run_ideagent.py --config configs/ideagent_opencode.yaml
```

For a quick plumbing check instead of a real topic, type:

```text
/ideagent smoke
```

To open the OpenCode TUI automatically from Python, you can still use:

```bash
python scripts/run_ideagent_in_opencode.py
```

To force a specific OpenCode model for that launcher:

```bash
python scripts/run_ideagent_in_opencode.py --model ollama/gpt-oss:120b
```

All OpenCode modes include live role progress lines for `ideator`, `critic`, `quality`,
`steno`, and `judge`.

To route calls through OpenCode instead of setting provider API keys in IDEAgent, use
the headless/backend wrapper:

```bash
python scripts/run_ideagent_opencode.py
```

The wrapper reuses OpenCode if it is already listening at `localhost:4096`; otherwise it
opens the OpenCode TUI first so you can choose the model from `/models` or the model
dropdown. After you select the model, quit OpenCode and the wrapper starts
`opencode serve --port 4096`, waits for it, runs IDEAgent, and shuts down the server it
launched. It uses:

```bash
python scripts/run_ideagent.py --config configs/ideagent_opencode_smoke.yaml
```

The OpenCode config omits `agents.*.model_id`, so OpenCode uses the model selected in
its interface/config. To skip the model picker and use OpenCode's saved/default model:

```bash
python scripts/run_ideagent_opencode.py --skip-model-picker
```

### Ollama backend

To route calls straight to local Ollama with no provider API key:

```bash
ollama pull llama3.2
python scripts/run_ideagent_ollama.py --model llama3.2
```

The wrapper reuses Ollama if it is already listening at `localhost:11434`; otherwise it
starts `ollama serve`, waits for it, runs IDEAgent, and shuts down the server it
launched. If `--model` is omitted, it uses `$OLLAMA_MODEL`, then the first installed
Ollama model from `/api/tags`.

### vLLM baseline backend

To run the baseline ladders against a local vLLM OpenAI-compatible server instead of
hosted LLM providers:

```bash
python scripts/run_baseline_vllm.py --mode stateless --model Qwen/Qwen2.5-7B-Instruct
```

Modes are `stateless`, `single-shot`, `sequential`, and `nova`. The wrapper reuses vLLM
if it is already listening at `localhost:8000`; otherwise it starts:

```bash
vllm serve Qwen/Qwen2.5-7B-Instruct --port 8000
```

All generator, steno, and judge roles in the selected baseline are pointed at that same
local vLLM model, so no `OPENAI_API_KEY`, `GEMINI_API_KEY`, or `ANTHROPIC_API_KEY` is
needed.

## ?? Run IDEAgent (main system)

```bash
python scripts/run_ideagent.py --config configs/ideagent.yaml
```

## ?? Run a Baseline

```bash
# Stateless-independent or single-shot batch
python baselines/simple/run_simple_baseline.py --config baselines/simple/stateless.yaml
python baselines/simple/run_simple_baseline.py --config baselines/simple/single_shot.yaml

# Sequential-memory
python baselines/simple/sequential_memory.py --config baselines/simple/sequential_memory.yaml

# NOVA closed-book
python baselines/nova/run_nova_closed_book.py --config baselines/nova/nova_closed_book.yaml
```

## ?? Evaluate

Runs both quality and diversity eval in one command:

```bash
python scripts/eval_ideas.py \
    --config configs/comp_quality_eval_opus47.yaml configs/diversity_eval_opus47.yaml \
    --input <final_idea_cores.jsonl> \
    --quality-output <quality_report.jsonl> \
    --diversity-output <diversity_report.jsonl> \
    --resume
```

Pass `--skip-quality` or `--skip-diversity` to run only one half. `--start-idx`/
`--end-idx` slice the topic list for sharding a run. `--max-workers` overrides
both evaluators' concurrency.

## ?? Results

Mean Yield across 32 topics spanning 8 CS domains. Yield(?) is the size of the
largest mutually-diverse (pairwise diversity ? 7) subset of an archive that is
simultaneously sound (? 7), clear (? 6), and non-obvious (? ?); Yield(?=7) is the
primary metric reported in the paper.

| Method                 | Yield (?=7, primary) | Yield (?=6) |
| ----------------------- | :-------------------: | :----------: |
| **IDEAgent (ours)**     | **1.09**               | **2.31**     |
| NOVA Closed-Book        | 0.28                   | 1.16         |
| Stateless-Independent   | 0.25                   | 0.81         |
| Sequential-Memory       | 0.19                   | 0.53         |
| Single-Shot Batch       | 0.00                   | 0.00         |

IDEAgent outperforms the best baseline (NOVA) by **3.89?** on Yield(?=7).

## ?? Examples

`data/examples/` holds sample generations from IDEAgent and every baseline, one
JSONL file per method, over the same fixed set of topics for direct comparison.

## ?? Citation

```bibtex
@misc{gumma2026ideagentagenticqualitydiversitysearch,
      title={IDEAgent: Agentic Quality-Diversity Search for Research Idea Generation}, 
      author={Varun Gumma and Navonil Majumder and Soumitra Sinhahajari and Soujanya Poria},
      year={2026},
      eprint={2607.22375},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2607.22375}, 
}
```
