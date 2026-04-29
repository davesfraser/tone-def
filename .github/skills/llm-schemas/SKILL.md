---
name: llm-schemas
description: >
  Pydantic schemas, structured outputs, Instructor, response models, tool
  schemas, validation retries, schema versioning.
user-invocable: true
---

# LLM Schemas - ToneDef

# ai-assistant-quick-summary

- Design schemas before prompts.
- Put schemas in `src/tonedef/schemas/`.
- Use strict Pydantic models.
- Describe fields clearly.
- Version breaking schema changes.

# schema-rules

RULE: Define reusable structured outputs as Pydantic models.
RULE: Use `Field(..., description=...)` because descriptions guide the model.
RULE: Keep schemas stable once downstream code or evals depend on them.
RULE: Version or rename schemas when removing fields or changing meanings.
RULE: Let Instructor handle validation retry rather than parsing free text manually.
