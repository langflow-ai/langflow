# lfx-google-genai

Google Gemini chat model and embeddings.

Part of the Google split (4-way separation of the legacy `lfx.components.google` directory).

## Components

| Class | Module |
| --- | --- |
| `GoogleGenerativeAIComponent` | `google_generative_ai` |
| `GoogleGenerativeAIEmbeddingsComponent` | `google_generative_ai_embeddings` |

## Install

```bash
pip install lfx-google-genai
```

## Develop

```bash
cd src/bundles/google_genai
pip install -e .
lfx extension validate src/lfx_google_genai
```

## Migration

Saved flows that referenced `lfx.components.google.*` for one of this bundle's components rewrite to `ext:google_genai:<Class>@official` via the migration table at `src/lfx/src/lfx/extension/migration/migration_table.json`.
