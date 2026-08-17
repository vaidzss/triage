# config.py - central knobs for the triage system.
#
# All LLM calls go through a single Ollama endpoint. Ollama itself proxies
# both locally-resident models and its "-cloud" hosted models through the
# same OpenAI-compatible API, so there is only ever one base_url/client here
# (unlike vaidz-llm/backend/agent_core.py, which has genuinely separate
# local/cloud providers).
#
# Known landmine (see vaidz-llm/backend/CLAUDE.md:114-116): gemma3:4b and
# plain llama3 return HTTP 400 "does not support tools". Do not use them for
# any model role below.

import os

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY", "ollama")

# Confirmed tool-capable (validated via scripts/validate_tool_calling.py),
# fits the 6GB VRAM RTX 3050 laptop GPU locally.
LOCAL_MODEL = os.environ.get("TRIAGE_LOCAL_MODEL", "qwen2.5:7b")

# Ollama's cloud proxy was the planned higher-quality fallback for patch
# generation, but the model this was validated against (qwen3-coder:480b-cloud)
# was retired by Ollama on 2026-07-15. Left unset by default; set
# TRIAGE_CLOUD_MODEL to a currently-available "-cloud" model to opt back in
# once one has been picked and re-validated with validate_tool_calling.py.
CLOUD_MODEL = os.environ.get("TRIAGE_CLOUD_MODEL", "")

# Which model each agent role uses by default. Override via env vars so the
# local-vs-cloud comparison (Phase 4) doesn't require code changes.
LOCATOR_MODEL = os.environ.get("TRIAGE_LOCATOR_MODEL", LOCAL_MODEL)
PATCHER_MODEL = os.environ.get("TRIAGE_PATCHER_MODEL", LOCAL_MODEL)

# Test-verification retry loop.
MAX_RETRIES = int(os.environ.get("TRIAGE_MAX_RETRIES", "3"))

# Sandbox execution.
SANDBOX_TIMEOUT_SECONDS = int(os.environ.get("TRIAGE_SANDBOX_TIMEOUT", "60"))
SANDBOX_BASE_IMAGE = os.environ.get("TRIAGE_SANDBOX_IMAGE", "python:3.11-slim")
