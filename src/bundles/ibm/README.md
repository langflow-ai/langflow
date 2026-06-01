# lfx-ibm

IBM components — Db2 Vector Store plus watsonx.ai LLM and embeddings — as a
standalone Langflow Extension Bundle.

This bundle ships three components:

* **`DB2VectorStoreComponent`** — wraps the `DB2VS` LangChain-compatible
  vector store and exposes Db2's native vector search through Langflow's
  standard vector-store palette entry.
* **`WatsonxAIComponent`** — chat/text-generation against IBM watsonx.ai
  foundation models via `langchain-ibm`'s `ChatWatsonx`.
* **`WatsonxEmbeddingsComponent`** — embeddings via watsonx.ai's
  `WatsonxEmbeddings` model.

It follows the documented porting recipe in
[`src/bundles/PORTING.md`](../PORTING.md).

## Install

```bash
pip install lfx-ibm
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. After install, restart your Langflow server; the three
components appear in the palette under the `ibm` bundle group.

> **Platform notes:**
> * The `ibm-db` driver does not ship a prebuilt wheel for
>   `linux/aarch64`; the dep is gated with a marker so `pip install`
>   succeeds on that architecture, but `DB2VectorStoreComponent` will
>   fail to build the vector store at runtime there. Use an x86_64 image
>   or install `ibm-db` from source if you need Db2 on aarch64.
> * `ibm-watsonx-ai` and `langchain-ibm` upstream pin `<3.14`. The marker
>   gates both deps the same way, so the watsonx components are only
>   importable on Python 3.13 and below until upstream lifts the cap.

## Develop

```bash
cd src/bundles/ibm
pip install -e .
lfx extension validate src/lfx_ibm
```

## Manifest

The extension manifest is shipped at `src/lfx_ibm/extension.json` and
points at the bundle at `components/ibm`. Components register under the
canonical namespaced IDs:

* `ext:ibm:DB2VectorStoreComponent@official`
* `ext:ibm:WatsonxAIComponent@official`
* `ext:ibm:WatsonxEmbeddingsComponent@official`

## Migration

Saved flows referencing the legacy bare class names
(`DB2VectorStoreComponent`, `WatsonxAIComponent`,
`WatsonxEmbeddingsComponent`) or the old import paths
(`lfx.components.ibm.<module>.<Class>` and the package-level
`lfx.components.ibm.<Class>` forms) are rewritten to the new namespaced
IDs by the migration table in
`src/lfx/src/lfx/extension/migration/migration_table.json`.
