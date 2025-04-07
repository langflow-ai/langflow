---
title: Integrate hybrid search with the Astra DB component
slug: /astra-db-hybrid-search
---


The **Astra DB** component includes **Hybrid search** enabled by default.

* Vector search searches by vector similarity.
* Lexical search finds matches by term.
* Hybrid search combines vector and lexical search with a re-ranker

** Hybrid search** passes a lexical query and a vector search together to return the most semantically relevant to the query. This uses the "find and rerank" Data API command.
A score is assigned for each query and document pair, and higher scores indicate a stronger match.
The strongest matches are passed on to the model component, 