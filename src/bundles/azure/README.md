# lfx-azure

Azure OpenAI components and Azure AI Foundry runtime support as a standalone
Langflow Extension Bundle.

## Install

```bash
pip install lfx-azure
```

`pip install langflow` includes this bundle because Azure AI Foundry is a
supported model provider. The bundle is registered automatically through the
`langflow.extensions` entry point and appears under the `azure` group with
canonical component IDs such as
`ext:azure:AzureChatOpenAIComponent@official`.

## Develop

```bash
uv sync
uv run pytest src/bundles/azure/tests -q
uv run lfx extension validate src/bundles/azure/src/lfx_azure
```

The bundle graduated from the manifest-less `lfx-bundles[azure]` provider in
Langflow 1.12. Its bundle and class names are unchanged, so existing saved
flows retain their canonical IDs.
