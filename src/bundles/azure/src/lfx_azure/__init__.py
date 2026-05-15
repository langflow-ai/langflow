"""lfx-azure: Azure bundle.

Distribution unit ``lfx-azure``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:azure:<Class>@official``.
"""

from lfx_azure.components.azure.azure_openai import AzureChatOpenAIComponent
from lfx_azure.components.azure.azure_openai_embeddings import AzureOpenAIEmbeddingsComponent

__all__ = [
    "AzureChatOpenAIComponent",
    "AzureOpenAIEmbeddingsComponent",
]
