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
  `https://openrouter.ai/api` or `http://localhost:8000` (required). The bundle's
  provider manifest declares `base_url_suffix: /v1`, so Langflow appends `/v1`
  when it is missing and preserves endpoints that already include it.
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

## Nebius Serverless Endpoint

Use this provider to connect Langflow to a model you deploy on a
[Nebius Serverless Endpoint](https://docs.nebius.com/serverless/overview).
This example uses a vLLM container serving `Qwen/Qwen3-0.6B`. Langflow runs
separately and sends inference requests to the Endpoint's managed HTTPS URL.
It does not create, start, stop, or delete cloud resources.

This configuration is for user-deployed Serverless Endpoints. Nebius Token
Factory / AI Studio managed model APIs use different credentials and URLs.
Serverless Jobs are finite workloads without a public inference URL, so they
cannot be used as this provider's Base URL.

### Prepare the Endpoint

1. Follow the [vLLM Nebius Serverless guide](https://docs.vllm.ai/en/latest/deployment/frameworks/nebius/)
   to deploy the model. It includes image/model versions, GPU requirements,
   readiness checks, and cleanup instructions. Creating an Endpoint allocates
   billable resources; use your own project and resource limits.
2. Configure token authentication with one HTTP port. Save the Endpoint ID and
   its authentication token. The Endpoint token is separate from your Nebius
   CLI/IAM credentials and from a Langflow API key.
3. Wait for the model to load. Copy the managed HTTPS URL from the Endpoint's
   **Public endpoints** field, rather than a VM IP address. A `RUNNING` status
   or an assigned URL alone does not prove the model is ready.

For example, check readiness from a machine that can reach the Endpoint:

```bash
export ENDPOINT_URL="https://<your-endpoint-host>"
# Set AUTH_TOKEN securely to the token configured on this Endpoint.

curl --fail-with-body --silent --show-error --max-time 10 \
  "${ENDPOINT_URL%/}/health" -H "Authorization: Bearer $AUTH_TOKEN"
curl --fail-with-body --silent --show-error --max-time 10 \
  "${ENDPOINT_URL%/}/v1/models" -H "Authorization: Bearer $AUTH_TOKEN"
```

Wait until both requests succeed and the model list includes
`Qwen/Qwen3-0.6B`. If you deployed a different model or served-name alias, use
the exact `id` returned by `/v1/models` instead. Verify that requests without
the token and with an incorrect token are rejected. The managed ingress
provides authentication; restrict any direct subnet access separately.

### Configure Langflow and run the flow

Install the bundle as described above if it is not already included in your
Langflow installation. Restart the backend after installing it.

1. Open **Settings → Model Providers → OpenAI Compatible**.
2. Set **Base URL** to the managed HTTPS URL and **API Key** to the Endpoint
   token. The provider accepts a URL with or without a final `/v1`, including
   a trailing slash; it uses exactly one `/v1` for these forms. Do not append
   `/models` or `/chat/completions` to Base URL.
3. Validate the settings, refresh the model list, and enable the served model.
4. Download and import [Nebius Endpoint Chat](examples/nebius-serverless-chat.json)
   into Langflow. It connects **Chat Input → Language Model → Chat Output**.
   Select your enabled **OpenAI Compatible** model in the Language Model node;
   leave its API Key override blank to use the provider settings.
5. Open Playground and send `Say hello in one short sentence. /no_think`.
   The example uses temperature `0` and a `512` token limit. `/no_think` is
   specific to the example Qwen model; adapt the prompt for other models.
6. After a successful response, enable **Stream** on the Language Model node
   and repeat. Check that output arrives incrementally and completes.

Alternatively, set these variables in the **Langflow backend's** environment
before starting it:

```bash
export OPENAI_COMPATIBLE_BASE_URL="$ENDPOINT_URL"
export OPENAI_COMPATIBLE_API_KEY="$AUTH_TOKEN"
```

Saved provider settings can take precedence over the environment. If a change
does not take effect, check the executing user's settings, restart the backend
when changing its environment, and refresh models. Keep tokens out of exported
flows, source control, screenshots, and logs. The example contains no Endpoint
URL or token. Its input/output nodes keep Langflow's default chat-history
storage enabled so Playground receives message events. Prompts and responses
are saved in Langflow; delete test sessions after validation. Disabling Chat
Output's **Store Messages** can prevent replies from appearing in Playground.

### Capabilities and troubleshooting

- **Empty model picker:** discovery has a five-second timeout and can return
  an empty list on connection, authentication, or parsing errors. Check the
  Endpoint's status/logs and authenticated `/v1/models` response. Discovery
  does not follow redirects. Configure Langflow after the model is ready.
- **Authentication errors:** use the Endpoint token, not an IAM token or
  managed model API key. A successful settings check probes `/v1/models`;
  test chat separately.
- **Wrong model or unsupported operation:** model discovery does not prove
  tool-calling or embedding support. This Qwen example is for chat. Models
  appear in both Language Model and Embedding Model pickers, but embeddings
  require an independently validated embedding model/server. The provider
  holds only one endpoint at a time; see [Configure](#configure) for options
  when chat and embeddings use different URLs.
- **Interrupted stream:** a partial response is incomplete. Inspect the
  inference server and ingress logs before retrying; cancelling a request
  does not stop the Endpoint.

### Stop serving and preserve application state

Stop or delete the Endpoint explicitly using the linked deployment guide.
Closing Langflow does not stop billing for a running Endpoint. After starting
a stopped Endpoint, retrieve its current URL and repeat readiness checks
before refreshing Langflow's provider configuration. This example does not
configure autoscaling or automatic scale-to-zero.

Keep Langflow's database/configuration on persistent storage independently of
the model Endpoint. Do not rely on the Endpoint's container disk to preserve
model downloads across stop/start. See [Endpoint management](https://docs.nebius.com/serverless/endpoints/manage)
for lifecycle and storage options.

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
