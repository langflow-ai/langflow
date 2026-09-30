# lfx-vllm

[vLLM](https://docs.vllm.ai/) as a first-class Langflow model provider, packaged
as a standalone Extension Bundle.

Registers a **vLLM** model provider that appears in Langflow's unified model
picker alongside the built-in providers. vLLM serves an OpenAI-compatible HTTP
API, so the provider reuses the `ChatOpenAI` / `OpenAIEmbeddings` classes and
discovers the served models live from the server's `/v1/models` endpoint — the
same model is therefore offered in both the **Language Model** and **Embedding
Model** contexts.

Unlike a component bundle, this ships **no component**: it contributes a
provider through the `providers[]` block in `extension.json`, which Langflow's
provider registry merges into the unified model system. It edits no Langflow
core files.

## Configure

Set the vLLM endpoint (and, if your server requires it, an API key) under
**Settings → Model Providers → vLLM**, or via environment variables:

- `VLLM_API_BASE` — base URL of your vLLM server, e.g. `http://localhost:8000`
  (required).
- `VLLM_API_KEY` — bearer token, if your server enforces one (optional; servers
  without auth do not need it).

## Install

```bash
pip install lfx-vllm
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. Restart your Langflow server and select **vLLM** in any Language
Model or Embedding Model field.

## Develop

```bash
cd src/bundles/vllm
pip install -e .
lfx extension validate src/lfx_vllm
```

## Credit

Inherits the original vLLM provider contributed in
[#13910](https://github.com/langflow-ai/langflow/pull/13910) by
**Yash Pareek** (@pareek-ml). This bundle reconstructs that work on the
provider-registry extension point so it ships without editing Langflow core.
