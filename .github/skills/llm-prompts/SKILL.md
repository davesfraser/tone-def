---
name: llm-prompts
description: >
  Prompt templates, system prompts, Jinja prompts, few-shot examples,
  prompt versions, prompt evals, prompt diffs, prompt caching.
user-invocable: true
---

# LLM Prompts - ToneDef

# ai-assistant-quick-summary

- Prompts are source code.
- Store reusable prompts as Jinja files.
- Declare every template variable.
- Link prompt changes to eval evidence.
- Keep examples outside long system prompts.

# prompt-files

RULE: Store prompts in `src/tonedef/prompt_templates/*.jinja`.
RULE: Give every prompt a header with author, version, eval_metric, and last_modified.
RULE: Render prompts with `render_prompt`; do not hand-roll template loading.
RULE: Keep few-shot examples in separate prompt or data files when they are reused.
RULE: Do not concatenate untrusted user input into instructions.

# review

RULE: A prompt PR must include an eval result, a cassette update, or a clear reason no eval applies.
RULE: Keep prompt wording in Australian English unless the product specifically requires another locale.
