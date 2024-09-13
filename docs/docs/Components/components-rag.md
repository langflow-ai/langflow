---
title: RAG
sidebar_position: 9
slug: /components-rag
---

RAG (Retrieval-Augmented Generation) components process a user query by retrieving relevant documents and generating a concise summary that addresses the user's question.

## Vectara RAG

This component leverages Vectara's Retrieval Augmented Generation (RAG) capabilities to search and summarize documents based on the provided input. For more information, see the [Vectara documentation](https://docs.vectara.com/docs/).

### Parameters

#### Inputs

| Name                  | Type         | Description                                                |
|-----------------------|--------------|------------------------------------------------------------|
| vectara_customer_id   | String       | Vectara customer ID                                        |
| vectara_corpus_id     | String       | Vectara corpus ID                                          |
| vectara_api_key       | SecretString | Vectara API key                                            |
| search_query          | String       | The query to receive an answer on                          |
| lexical_interpolation | Float        | Hybrid search factor (0.005 to 0.1)                        |
| filter                | String       | Metadata filters to narrow the search                      |
| reranker              | String       | Reranker type (mmr, rerank_multilingual_v1, none)          |
| reranker_k            | Integer      | Number of results to rerank (1 to 100)                     |
| diversity_bias        | Float        | Diversity bias for MMR reranker (0 to 1)                   |
| max_results           | Integer      | Maximum number of search results to summarize (1 to 100)   |
| response_lang         | String       | Language code for the response (e.g., "eng", "auto")       |
| prompt                | String       | Prompt name for summarization                              |

#### Outputs

| Name   | Type    | Description           |
|--------|---------|-----------------------|
| answer | Message | Generated RAG response|