# lfx-acedatacloud

A Langflow Extension Bundle submitted for the default distribution with one Ace Data Cloud chat model provider, 17 independent service actions, and 15 task readers. Install it in the Langflow environment with `uv pip install lfx-acedatacloud` when the package is published on PyPI, then restart Langflow. Until then, install the [public v0.1.2 GitHub wheel](https://github.com/AceDataCloud/LangflowAceDataCloud/releases/tag/v0.1.2) in the same environment. Confirm the bundle with `lfx extension list`.

The package registers one `ace_data_cloud` bundle and the named **Ace Data Cloud** model provider. API keys belong in a Langflow Credential global variable named `ACEDATACLOUD_API_KEY`. The components send requests only to `https://api.acedata.cloud`, never retry paid submissions automatically, and provide separate task lookup for asynchronous services. Media generation defaults to asynchronous submission; GPT Image, Midjourney, and Veo task readers also accept a trace ID from request history when a paid submission returned no task ID. Model discovery intersects the public `type=chat` catalog with the models visible to the configured key, so new text models do not require a bundle release. The catalog does not provide per-model tool support, so Agent tool calling is not advertised.

The [step-by-step English and Chinese guide](https://github.com/AceDataCloud/LangflowAceDataCloud) includes no-key flow JSONs, real Langflow screenshots, and sanitized task and Credits readbacks. The 17 service components expose reviewed first-run actions; they do not claim full parity with every advanced Ace Data Cloud API action.

## API key setup

Register or sign in at [Applications](https://platform.acedata.cloud/console/applications?utm_source=opensource&utm_medium=referral&utm_campaign=evergreen&utm_content=langflow_bundle_readme_api_key). Initialize General application if needed, then use **Keys / Manage Keys → Create** to name a key, review expiration/usage/API limits, and copy the token. Save the raw value as the Langflow Credential global variable `ACEDATACLOUD_API_KEY`; do not add `Bearer ` or use an account-management token. The [illustrated setup guide](https://github.com/AceDataCloud/LangflowAceDataCloud#2-create-an-api-key-with-the-right-access) shows the complete flow.

Default inclusion is requested in [the open Langflow PR](https://github.com/langflow-ai/langflow/pull/15659); it is not claimed live before maintainer acceptance and release. The public v0.1.2 wheel is a documentation release for Langflow 1.12.5. The 0.1.3 bundle in this pending upstream PR also includes separately reviewed model-discovery behavior; those runtime changes are not claimed present in v0.1.2.

## Development

```bash
uv pip install -e src/bundles/acedatacloud
lfx extension validate src/bundles/acedatacloud/src/lfx_acedatacloud --execute-imports
pytest -q src/bundles/acedatacloud/tests
```

## Find a service

Search the component palette for Suno, Seedance, HappyHorse, GPT Image, or Nano Banana. The service-first nodes say **by Ace Data Cloud** and keep generation separate from read-only task retrieval. Service-specific walkthroughs are linked from [the bundle guide](https://docs.langflow.org/bundles-acedatacloud). Each node points to its own guide; class IDs and saved-flow bundle identity stay stable.
