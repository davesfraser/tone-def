---
name: llm-testing
description: >
  LLM tests, pytest-recording, VCR cassettes, respx mocks, snapshots,
  no live API CI, cassette refreshes, secret filtering.
user-invocable: true
---

# LLM Testing - ToneDef

# ai-assistant-quick-summary

- Default tests never call live APIs.
- Mock unit tests first.
- Use cassettes for recorded integration tests.
- Filter secrets from cassettes.
- Review cassette diffs like source code.

# test-policy

RULE: `uv run pytest --record-mode=none` must pass without API keys.
RULE: Use `respx` or monkeypatching for unit tests around provider calls.
RULE: Use `pytest-recording` only for HTTP replay, not runtime response caching.
RULE: Keep cassettes in `tests/cassettes/`.
RULE: Never commit cassettes containing auth headers, API keys, or personal data.
RULE: Mark live provider tests with `live_api` and keep them out of default CI.

# cassette-refresh

RULE: Refresh cassettes deliberately with a real key, review the diff, then restore `--record-mode=none`.
