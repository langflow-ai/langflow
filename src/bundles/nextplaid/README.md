# lfx-nextplaid

NextPlaid multi-vector vector store (plus its companion vLLM multivector
embeddings) as a standalone Langflow Extension Bundle.

NextPlaid stores each document as a *matrix* of token embeddings rather than
a single vector, enabling ColBERT/ColPali-style late interaction (MaxSim
scoring) for significantly higher retrieval quality on semantic search.
The bundle ships two components:

- **`NextPlaidVectorStoreComponent`** — vector store backed by a running
  [NextPlaid server](https://github.com/meetdoshi90/next-plaid) via the
  [`langchain-plaid`](https://pypi.org/project/langchain-plaid/) client.
  Supports text (ColBERT) and image (ColPali) ingestion with full upsert
  semantics via stable document IDs.
- **`VllmMultivectorEmbeddingsComponent`** — produces the token-matrix
  embeddings NextPlaid ingests by calling vLLM's `/pooling` endpoint with
  `task: token_embed`. Compatible with ColBERT models such as
  `answerdotai/answerai-colbert-small-v1`.

## Requirements

- A running [NextPlaid server](https://github.com/meetdoshi90/next-plaid).
- A running [vLLM server](https://docs.vllm.ai/) with a ColBERT-compatible
  model loaded via `--runner pooling`.

## Install

```bash
pip install lfx-nextplaid
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. After install, restart your Langflow server; the components
appear in the palette under the `nextplaid` bundle group.

## Develop

```bash
cd src/bundles/nextplaid
pip install -e .
lfx extension validate src/lfx_nextplaid
```

## Manifest

The extension manifest is shipped at `src/lfx_nextplaid/extension.json` and
points at the bundle at `components/nextplaid`. Components register under the
canonical namespaced IDs `ext:nextplaid:NextPlaidVectorStoreComponent@official`
and `ext:nextplaid:VllmMultivectorEmbeddingsComponent@official`.

## Migration

Saved flows referencing the legacy class names or the old import paths under
`lfx.components.nextplaid.*` / `lfx.components.vllm.VllmMultivectorEmbeddingsComponent`
are rewritten to the new namespaced IDs by the migration table in
`src/lfx/src/lfx/extension/migration/migration_table.json`.
