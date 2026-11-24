# lfx-ollama

Ollama language-model and embedding components as a standalone Langflow
Extension Bundle.

## Install

```bash
pip install lfx-ollama
```

`pip install langflow` includes this bundle because Ollama is a supported model
provider. The bundle is registered automatically through the
`langflow.extensions` entry point and appears under the `ollama` group with
canonical component IDs such as `ext:ollama:ChatOllamaComponent@official`.

## Develop

```bash
uv sync
uv run pytest src/bundles/ollama/tests -q
uv run lfx extension validate src/bundles/ollama/src/lfx_ollama
```

The bundle graduated from the manifest-less `lfx-bundles[ollama]` provider in
Langflow 1.12. Its bundle and class names are unchanged, so existing saved
flows retain their canonical IDs.
