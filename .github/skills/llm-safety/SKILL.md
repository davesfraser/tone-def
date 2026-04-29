---
name: llm-safety
description: >
  Prompt injection, untrusted input, guardrails, refusal schemas, PII,
  data leakage, logging, tracing, tool safety.
user-invocable: true
---

# LLM Safety - ToneDef

# ai-assistant-quick-summary

- Treat user input as untrusted.
- Treat retrieved context as untrusted.
- Validate model outputs.
- Redact before logging or tracing.
- Define refusal behaviour explicitly.

# safety-rules

RULE: Never place user input or retrieved text inside privileged instructions.
RULE: Separate system instructions from user data.
RULE: Validate inputs before LLM calls when they control retrieval, tools, or file paths.
RULE: Validate outputs against schemas before acting on them.
RULE: Redact secrets and personal data before writing traces, logs, eval rows, or cassettes.
RULE: Use refusal schemas that distinguish cannot answer, should not answer, and needs human review.
