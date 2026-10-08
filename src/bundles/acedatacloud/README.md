# lfx-acedatacloud

An opt-in Langflow Extension Bundle with one Ace Data Cloud chat model provider, 17 independent service actions, and 15 task readers. Install it in the Langflow environment with `uv pip install lfx-acedatacloud` when the package is published on PyPI, then restart Langflow. Until then, install the [public v0.1.1 GitHub wheel](https://github.com/AceDataCloud/LangflowAceDataCloud/releases/tag/v0.1.1) in the same environment. Confirm the bundle with `lfx extension list`.

The package registers one `ace_data_cloud` bundle and the named **Ace Data Cloud** model provider. API keys belong in a Langflow Credential global variable named `ACEDATACLOUD_API_KEY`. The components send requests only to `https://api.acedata.cloud`, never retry paid submissions automatically, and provide separate task lookup for asynchronous services. Media generation defaults to asynchronous submission; GPT Image, Midjourney, and Veo task readers also accept a trace ID from request history when a paid submission returned no task ID.

The [step-by-step English and Chinese guide](https://github.com/AceDataCloud/LangflowAceDataCloud) includes no-key flow JSONs, real Langflow screenshots, and sanitized task and Credits readbacks. The 17 service components expose reviewed first-run actions; they do not claim full parity with every advanced Ace Data Cloud API action.

## Development

```bash
uv pip install -e src/bundles/acedatacloud
lfx extension validate src/bundles/acedatacloud/src/lfx_acedatacloud --execute-imports
pytest -q src/bundles/acedatacloud/tests
```
