---
name: llm-rag
description: >
  RAG, retrieval, vector stores, Chroma, Qdrant, pgvector, embeddings,
  chunking, hybrid search, reranking, citations, retrieval evals.
user-invocable: true
---

# LLM RAG - ToneDef

# ai-assistant-quick-summary

- Treat indexes as rebuildable artefacts.
- Evaluate retrieval before generation.
- Keep source chunk IDs with every answer.
- Start with simple chunking, then tune by eval.
- Do not commit vector indexes.

# retrieval-rules

RULE: Use `indexes/` for local vector indexes and keep it out of git.
RULE: Keep source IDs attached to chunks from ingestion through final answer.
RULE: Test retrieval with recall at k and citation correctness before tuning prompts.
RULE: Use 512-token chunks with 10 to 20 percent overlap as a baseline, then tune from evals.
RULE: Use hybrid dense plus sparse retrieval for production systems when the store supports it.
RULE: Use reranking only when retrieval evals show ranking, not recall, is the bottleneck.

# selected-stack

The selected vector store is `chroma`.
Local embeddings are not enabled.
Reranking is not enabled.
