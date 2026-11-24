# lfx-acedatacloud

An optional Langflow extension with an Ace Data Cloud model provider, service actions and task readers. Install the published [0.1.4 package](https://pypi.org/project/lfx-acedatacloud/0.1.4/) for Chat Completions and media components. Release 0.1.4 starts with five suggested chat models and can fetch models for a saved credential. The [GitHub release](https://github.com/AceDataCloud/LangflowAceDataCloud/releases/tag/v0.1.4) also contains five service-only distributions.

This checkout contains the unreleased 0.1.5.dev0 bundle. Install the local directory using the development command below to use protocol-aware discovery and native Messages.

The package registers one `ace_data_cloud` bundle and the named **Ace Data Cloud** model provider. API keys belong in a Langflow Credential global variable named `ACEDATACLOUD_API_KEY`. The components send requests only to `https://api.acedata.cloud`, never retry paid submissions automatically, and provide separate task lookup for asynchronous services. Media generation defaults to asynchronous submission; GPT Image, Midjourney, and Veo task readers also accept a trace ID from request history when a paid submission returned no task ID. Model discovery loads the complete public `type=chat` catalog before a key is entered and intersects it with the models visible to the configured key afterward. New models and their Chat Completions, Responses, or Messages protocols do not require a bundle release. The public catalog refreshes every five minutes; a temporary refresh failure retains the last valid catalog. Image-capable chat models remain available, while image-only and embedding APIs stay outside the chat selector. Native Messages uses Bearer authentication. Tool capabilities are explicitly unknown when the catalog does not declare them: the picker permits an explicit tool attempt without displaying verified support, and explicit `False` remains excluded. No context limit, pricing or capability data is borrowed from another provider with the same model name. Explicit custom base URLs keep the user's OpenAI-compatible settings.

The [step-by-step English and Chinese guide](https://github.com/AceDataCloud/LangflowAceDataCloud) includes no-key flow JSONs, real Langflow screenshots, and sanitized task and Credits readbacks. The 17 service components expose reviewed first-run actions; they do not claim full parity with every advanced Ace Data Cloud API action.

## API key setup

Register or sign in at [Applications](https://platform.acedata.cloud/console/applications?utm_source=opensource&utm_medium=referral&utm_campaign=evergreen&utm_content=langflow_bundle_readme_api_key). Initialize General application if needed, then use **Keys / Manage Keys → Create** to name a key, review expiration/usage/API limits, and copy the token. Save the raw value as the Langflow Credential global variable `ACEDATACLOUD_API_KEY`; do not add `Bearer ` or use an account-management token. The [illustrated setup guide](https://github.com/AceDataCloud/LangflowAceDataCloud#2-create-an-api-key-with-the-right-access) shows the complete flow.


## Development

```bash
uv pip install -e src/bundles/acedatacloud
lfx extension validate src/bundles/acedatacloud/src/lfx_acedatacloud --execute-imports
pytest -q src/bundles/acedatacloud/tests
```

## Find a service

Search the component palette for Suno, Seedance, HappyHorse, GPT Image, or Nano Banana. The service-first nodes say **by Ace Data Cloud** and keep generation separate from read-only task retrieval. Service-specific walkthroughs are linked from [the bundle guide](https://docs.langflow.org/bundles-acedatacloud). Each node points to its own guide; class IDs and saved-flow bundle identity stay stable.
