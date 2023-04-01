## LLM
from typing import Any

from langchain import llms, requests
from langchain.agents import agent_toolkits
from langchain.chat_models import ChatOpenAI

from langflow.interface.importing.utils import import_class

llm_type_to_cls_dict = llms.type_to_cls_dict
llm_type_to_cls_dict["openai-chat"] = ChatOpenAI


## Memory

# from langchain.memory.buffer_window import ConversationBufferWindowMemory
# from langchain.memory.chat_memory import ChatMessageHistory
# from langchain.memory.combined import CombinedMemory
# from langchain.memory.entity import ConversationEntityMemory
# from langchain.memory.kg import ConversationKGMemory
# from langchain.memory.readonly import ReadOnlySharedMemory
# from langchain.memory.simple import SimpleMemory
# from langchain.memory.summary import ConversationSummaryMemory
# from langchain.memory.summary_buffer import ConversationSummaryBufferMemory

memory_type_to_cls_dict: dict[str, Any] = {
    # "CombinedMemory": CombinedMemory,
    # "ConversationBufferWindowMemory": ConversationBufferWindowMemory,
    # "ConversationBufferMemory": ConversationBufferMemory,
    # "SimpleMemory": SimpleMemory,
    # "ConversationSummaryBufferMemory": ConversationSummaryBufferMemory,
    # "ConversationKGMemory": ConversationKGMemory,
    # "ConversationEntityMemory": ConversationEntityMemory,
    # "ConversationSummaryMemory": ConversationSummaryMemory,
    # "ChatMessageHistory": ChatMessageHistory,
    # "ConversationStringBufferMemory": ConversationStringBufferMemory,
    # "ReadOnlySharedMemory": ReadOnlySharedMemory,
}


## Chain
# from langchain.chains.loading import type_to_loader_dict
# from langchain.chains.conversation.base import ConversationChain

# chain_type_to_cls_dict = type_to_loader_dict
# chain_type_to_cls_dict["conversation_chain"] = ConversationChain

toolkit_type_to_loader_dict: dict[str, Any] = {
    toolkit_name: import_class(f"langchain.agents.agent_toolkits.{toolkit_name}")
    # if toolkit_name is lower case it is a loader
    for toolkit_name in agent_toolkits.__all__
    if toolkit_name.islower()
}

toolkit_type_to_cls_dict: dict[str, Any] = {
    toolkit_name: import_class(f"langchain.agents.agent_toolkits.{toolkit_name}")
    # if toolkit_name is not lower case it is a class
    for toolkit_name in agent_toolkits.__all__
    if not toolkit_name.islower()
}


wrapper_type_to_cls_dict: dict[str, Any] = {
    wrapper.__name__: wrapper for wrapper in [requests.RequestsWrapper]
}

## Embeddings
from langchain.embeddings import (
    CohereEmbeddings,
    FakeEmbeddings,
    HuggingFaceEmbeddings,
    HuggingFaceHubEmbeddings,
    HuggingFaceInstructEmbeddings,
    OpenAIEmbeddings,
    SelfHostedEmbeddings,
    SelfHostedHuggingFaceEmbeddings,
    SelfHostedHuggingFaceInstructEmbeddings,
    # SagemakerEndpointEmbeddings,
    TensorflowHubEmbeddings,
)

embedding_type_to_cls_dict = {
    "OpenAIEmbeddings": OpenAIEmbeddings,
    "HuggingFaceEmbeddings": HuggingFaceEmbeddings,
    "CohereEmbeddings": CohereEmbeddings,
    "HuggingFaceHubEmbeddings": HuggingFaceHubEmbeddings,
    "TensorflowHubEmbeddings": TensorflowHubEmbeddings,
    # "SagemakerEndpointEmbeddings": SagemakerEndpointEmbeddings,
    "HuggingFaceInstructEmbeddings": HuggingFaceInstructEmbeddings,
    "SelfHostedEmbeddings": SelfHostedEmbeddings,
    "SelfHostedHuggingFaceEmbeddings": SelfHostedHuggingFaceEmbeddings,
    "SelfHostedHuggingFaceInstructEmbeddings": SelfHostedHuggingFaceInstructEmbeddings,
    "FakeEmbeddings": FakeEmbeddings,
}

## Vector Stores
from langchain.vectorstores import (
    FAISS,
    AtlasDB,
    Chroma,
    DeepLake,
    ElasticVectorSearch,
    Milvus,
    OpenSearchVectorSearch,
    Pinecone,
    Qdrant,
    VectorStore,
    Weaviate,
)

vectorstores_type_to_cls_dict = {
    "ElasticVectorSearch": ElasticVectorSearch,
    "FAISS": FAISS,
    "VectorStore": VectorStore,
    "Pinecone": Pinecone,
    "Weaviate": Weaviate,
    "Qdrant": Qdrant,
    "Milvus": Milvus,
    "Chroma": Chroma,
    "OpenSearchVectorSearch": OpenSearchVectorSearch,
    "AtlasDB": AtlasDB,
    "DeepLake": DeepLake,
}

## Document Loaders

from langchain.document_loaders import (
    AirbyteJSONLoader,
    AZLyricsLoader,
    CollegeConfidentialLoader,
    CoNLLULoader,
    CSVLoader,
    DirectoryLoader,
    EverNoteLoader,
    FacebookChatLoader,
    GCSDirectoryLoader,
    GCSFileLoader,
    GitbookLoader,
    GoogleApiClient,
    GoogleApiYoutubeLoader,
    GoogleDriveLoader,
    GutenbergLoader,
    HNLoader,
    IFixitLoader,
    IMSDbLoader,
    NotebookLoader,
    NotionDirectoryLoader,
    ObsidianLoader,
    OnlinePDFLoader,
    PagedPDFSplitter,
    PDFMinerLoader,
    PyMuPDFLoader,
    PyPDFLoader,
    ReadTheDocsLoader,
    RoamLoader,
    S3DirectoryLoader,
    S3FileLoader,
    SRTLoader,
    TelegramChatLoader,
    TextLoader,
    UnstructuredEmailLoader,
    UnstructuredFileIOLoader,
    UnstructuredFileLoader,
    UnstructuredHTMLLoader,
    UnstructuredImageLoader,
    UnstructuredMarkdownLoader,
    UnstructuredPDFLoader,
    # BSHTMLLoader,
    UnstructuredPowerPointLoader,
    UnstructuredURLLoader,
    UnstructuredWordDocumentLoader,
    WebBaseLoader,
    YoutubeLoader,
)

documentloaders_type_to_cls_dict = {
    "UnstructuredFileLoader": UnstructuredFileLoader,
    "UnstructuredFileIOLoader": UnstructuredFileIOLoader,
    "UnstructuredURLLoader": UnstructuredURLLoader,
    "DirectoryLoader": DirectoryLoader,
    "NotionDirectoryLoader": NotionDirectoryLoader,
    "ReadTheDocsLoader": ReadTheDocsLoader,
    "GoogleDriveLoader": GoogleDriveLoader,
    "UnstructuredHTMLLoader": UnstructuredHTMLLoader,
    # "BSHTMLLoader": BSHTMLLoader,
    "UnstructuredPowerPointLoader": UnstructuredPowerPointLoader,
    "UnstructuredWordDocumentLoader": UnstructuredWordDocumentLoader,
    "UnstructuredPDFLoader": UnstructuredPDFLoader,
    "UnstructuredImageLoader": UnstructuredImageLoader,
    "ObsidianLoader": ObsidianLoader,
    "UnstructuredEmailLoader": UnstructuredEmailLoader,
    "UnstructuredMarkdownLoader": UnstructuredMarkdownLoader,
    "RoamLoader": RoamLoader,
    "YoutubeLoader": YoutubeLoader,
    "S3FileLoader": S3FileLoader,
    "TextLoader": TextLoader,
    "HNLoader": HNLoader,
    "GitbookLoader": GitbookLoader,
    "S3DirectoryLoader": S3DirectoryLoader,
    "GCSFileLoader": GCSFileLoader,
    "GCSDirectoryLoader": GCSDirectoryLoader,
    "WebBaseLoader": WebBaseLoader,
    "IMSDbLoader": IMSDbLoader,
    "AZLyricsLoader": AZLyricsLoader,
    "CollegeConfidentialLoader": CollegeConfidentialLoader,
    "IFixitLoader": IFixitLoader,
    "GutenbergLoader": GutenbergLoader,
    "PagedPDFSplitter": PagedPDFSplitter,
    "PyPDFLoader": PyPDFLoader,
    "EverNoteLoader": EverNoteLoader,
    "AirbyteJSONLoader": AirbyteJSONLoader,
    "OnlinePDFLoader": OnlinePDFLoader,
    "PDFMinerLoader": PDFMinerLoader,
    "PyMuPDFLoader": PyMuPDFLoader,
    "TelegramChatLoader": TelegramChatLoader,
    "SRTLoader": SRTLoader,
    "FacebookChatLoader": FacebookChatLoader,
    "NotebookLoader": NotebookLoader,
    "CoNLLULoader": CoNLLULoader,
    "GoogleApiYoutubeLoader": GoogleApiYoutubeLoader,
    "GoogleApiClient": GoogleApiClient,
    "CSVLoader": CSVLoader,
    # "BlackboardLoader",
}
