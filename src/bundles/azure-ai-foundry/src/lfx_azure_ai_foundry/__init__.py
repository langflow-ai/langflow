"""lfx-azure-ai-foundry: Azure AI Foundry model-provider bundle.

At runtime Langflow's loader discovers the ``extension.json`` shipped alongside
this ``__init__.py`` and registers its ``providers[]`` entry, merging an
**Azure AI Foundry** provider into the unified model system. The provider
uses ``AzureAIOpenAIApiChatModel`` from ``langchain-azure-ai`` and seeds a
static catalog of common Foundry deployment model names.
"""
