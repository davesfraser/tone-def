---
name: llm-api
description: >
  Provider routing and LLM API calls with LiteLLM, Instructor, streaming,
  async calls, retries, model strings, costs, rate limits, timeouts.
user-invocable: true
---

# LLM API - ToneDef

# ai-assistant-quick-summary

- Route LLM calls through `client.py`.
- Keep provider and model settings configurable.
- Use retries with explicit timeouts.
- Prefer structured outputs for reusable pipelines.
- Track cost and latency when behaviour matters.

# calling-rules

RULE: For new LLM code, do not call provider SDKs directly from notebooks, scripts, or app handlers.
RULE: Use `complete` or `acomplete` for plain text responses.
RULE: Use `complete_structured` or `acomplete_structured` with Pydantic schemas for reusable outputs.
RULE: Pin model strings in settings or environment variables, not inline code.
RULE: Catch provider errors at application boundaries and return typed failure states.
EXCEPTION: Existing ToneDef Anthropic call sites may stay on the direct SDK until a deliberate client migration changes them.
EXCEPTION: Use a direct provider SDK when a provider feature is unavailable through LiteLLM, and isolate it behind a small adapter.

# operations

RULE: Keep request timeouts and retry attempts in `settings.py`.
RULE: Capture token usage, latency, and estimated cost where the response object exposes them.
RULE: Treat streaming as an application interface decision, not a prompt decision.
