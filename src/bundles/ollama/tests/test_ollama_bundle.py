from langchain_ollama import ChatOllama, OllamaEmbeddings
from lfx_ollama import ChatOllamaComponent, OllamaEmbeddingsComponent


def test_ollama_bundle_exports_components_and_runtime_classes() -> None:
    assert ChatOllamaComponent.name == "OllamaModel"
    assert OllamaEmbeddingsComponent.name == "OllamaEmbeddings"
    assert ChatOllama.__name__ == "ChatOllama"
    assert OllamaEmbeddings.__name__ == "OllamaEmbeddings"
