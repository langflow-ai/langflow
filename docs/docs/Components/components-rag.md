---
title: RAG
sidebar_position: 9
slug: /components-rag
---

RAG (Retrieval-Augmented Generation) components process a user query by retrieving relevant documents and generating a concise summary that addresses the user's question.

### Vectara

`Vectara` performs RAG using a Vectara corpus, including document retrieval, reranking results, and summary generation.

**Parameters:**

- **Vectara Customer ID:** Customer ID.
- **Vectara Corpus ID:** Corpus ID.
- **Vectara API Key:** API key.
- **Search Query:** User query.
- **Lexical Interpolation:** How much to weigh lexical vs. embedding scores.
- **Metadata Filters:** Filters to narrow down the search documents and parts.
- **Reranker Type:** How to rerank the retrieved results.
- **Number of Results to Rerank:** Maximum reranked results.
- **Diversity Bias:** How much to diversify retrieved results (only for MMR reranker).
- **Max Results to Summarize:** Maximum search results to provide to summarizer.
- **Response Language:** The language code (use ISO 639-1 or 639-3 codes) of the summary.
- **Prompt Name:** The summarizer prompt.

For more information, consult the [Vectara documentation](https://docs.vectara.com/docs)
