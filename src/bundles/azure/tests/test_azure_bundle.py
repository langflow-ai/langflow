from langchain_azure_ai.chat_models import AzureAIOpenAIApiChatModel
from lfx_azure import AzureChatOpenAIComponent, AzureOpenAIEmbeddingsComponent


def test_azure_bundle_exports_components_and_foundry_runtime() -> None:
    assert AzureChatOpenAIComponent.name == "AzureOpenAIModel"
    assert AzureOpenAIEmbeddingsComponent.name == "AzureOpenAIEmbeddings"
    assert AzureAIOpenAIApiChatModel.__name__ == "AzureAIOpenAIApiChatModel"
