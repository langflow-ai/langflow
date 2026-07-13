# lfx-openai-compatible

Generic OpenAI-compatible endpoints as a first-class Langflow model provider,
packaged as a standalone Extension Bundle.

Registers an **OpenAI Compatible** model provider that appears in Langflow's
unified model picker alongside the built-in providers. Any service that speaks
the OpenAI HTTP API shape can be configured through it — for example:

| Provider | Base URL |
|----------|----------|
| OpenRouter | `https://openrouter.ai/api/v1` |
| Together AI | `https://api.together.xyz/v1` |
| Groq | `https://api.groq.com/openai/v1` |
| Fireworks AI | `https://api.fireworks.ai/inference/v1` |
| Self-hosted vLLM / TGI / LM Studio | `http://localhost:8000/v1` |

The provider reuses the `ChatOpenAI` / `OpenAIEmbeddings` classes and discovers
the served models live from the endpoint's `/v1/models` route — the same model
is therefore offered in both the **Language Model** and **Embedding Model**
contexts.

Unlike a component bundle, this ships **no component**: it contributes a
provider through the `providers[]` block in `extension.json`, which Langflow's
provider registry merges into the unified model system. It edits no Langflow
core files.

## Configure

Set the endpoint (and, if it requires one, an API key) under
**Settings → Model Providers → OpenAI Compatible**, or via environment
variables:

- `OPENAI_COMPATIBLE_BASE_URL` — base URL of the endpoint, e.g.
  `https://openrouter.ai/api/v1` or `http://localhost:8000/v1` (required).
- `OPENAI_COMPATIBLE_API_KEY` — bearer token, if the endpoint enforces one
  (optional; local servers without auth do not need it).

The provider holds one endpoint at a time. For a second concurrent custom
endpoint, combine it with the built-in OpenAI provider's Base URL override or
the vLLM provider (`lfx-vllm`).

## Install

```bash
pip install lfx-openai-compatible
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. Restart your Langflow server and select **OpenAI Compatible** in
any Language Model or Embedding Model field.

## Develop

```bash
cd src/bundles/openai-compatible
pip install -e .
lfx extension validate src/lfx_openai_compatible
```

## Credit

Resolves the feature request in
[#12839](https://github.com/langflow-ai/langflow/issues/12839). Follows the
provider-bundle pattern established by `lfx-vllm`
([#13919](https://github.com/langflow-ai/langflow/pull/13919)).
