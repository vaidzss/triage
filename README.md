# triage

Autonomous multi-agent code-repair system, SWE-bench style:

1. **Bug Locator** — finds the relevant file/function for an issue (ripgrep + tree-sitter).
2. **Patch Engineer** — proposes a fix as a unified diff.
3. **Test Verification** — runs the repo's test suite in a Docker sandbox; failures loop back to the Patch Engineer up to N retries.

Orchestrated as a LangGraph state machine. LLM calls go through Ollama's OpenAI-compatible
endpoint (`src/triage/llm_client.py`), configurable between a local model and a cloud-routed one
(`src/triage/config.py`).

## Prerequisites

- Docker Desktop running (engine must be up before using `src/triage/sandbox.py`).
- Ollama running locally with a tool-calling-capable model pulled, e.g. `ollama pull qwen2.5:7b`.
  `gemma3:4b` and plain `llama3` do **not** support tool calls (HTTP 400) — do not use them here.

## Setup

```
pip install -e ".[dev]"
```

## Status

Phase 0 (scaffolding + model validation), Phase 1 (Docker sandbox runner), and Phase 2
(LangGraph Patcher <-> Tester retry loop) done and checkpointed
(`pytest tests/` passes end-to-end against Docker + Ollama, including a full
bug -> patch -> tests-pass cycle in `tests/test_graph_single_bug.py`).
Next up: Phase 3, the Bug Locator (ripgrep + tree-sitter).
See the build plan for the full phased roadmap (Locator, benchmark harness).

Notes:
- `TRIAGE_CLOUD_MODEL` is unset by default — the originally planned cloud fallback
  (`qwen3-coder:480b-cloud`) was retired by Ollama on 2026-07-15. Everything currently
  runs on `qwen2.5:7b` locally.
