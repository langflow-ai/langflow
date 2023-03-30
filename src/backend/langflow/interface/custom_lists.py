## LLM
from typing import Any

from langchain import llms
from langchain.llms.openai import OpenAIChat

llm_type_to_cls_dict = llms.type_to_cls_dict
llm_type_to_cls_dict["openai-chat"] = OpenAIChat


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


## Embeddings
from langchain.embeddings import (
    CohereEmbeddings,
    FakeEmbeddings,
    HuggingFaceEmbeddings,
    HuggingFaceInstructEmbeddings,
    HuggingFaceHubEmbeddings,
    OpenAIEmbeddings,
    # SagemakerEndpointEmbeddings,
    TensorflowHubEmbeddings,
    SelfHostedHuggingFaceEmbeddings,
    SelfHostedHuggingFaceInstructEmbeddings,
    SelfHostedEmbeddings,
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
    ElasticVectorSearch,
    FAISS,
    VectorStore,
    Pinecone,
    Weaviate,
    Qdrant,
    Milvus,
    Chroma,
    OpenSearchVectorSearch,
    AtlasDB,
    DeepLake,
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
    UnstructuredFileLoader,
    UnstructuredFileIOLoader,
    UnstructuredURLLoader,
    DirectoryLoader,
    NotionDirectoryLoader,
    ReadTheDocsLoader,
    GoogleDriveLoader,
    UnstructuredHTMLLoader,
    # BSHTMLLoader,
    UnstructuredPowerPointLoader,
    UnstructuredWordDocumentLoader,
    UnstructuredPDFLoader,
    UnstructuredImageLoader,
    ObsidianLoader,
    UnstructuredEmailLoader,
    UnstructuredMarkdownLoader,
    RoamLoader,
    YoutubeLoader,
    S3FileLoader,
    TextLoader,
    HNLoader,
    GitbookLoader,
    S3DirectoryLoader,
    GCSFileLoader,
    GCSDirectoryLoader,
    WebBaseLoader,
    IMSDbLoader,
    AZLyricsLoader,
    CollegeConfidentialLoader,
    IFixitLoader,
    GutenbergLoader,
    PagedPDFSplitter,
    PyPDFLoader,
    EverNoteLoader,
    AirbyteJSONLoader,
    OnlinePDFLoader,
    PDFMinerLoader,
    PyMuPDFLoader,
    TelegramChatLoader,
    SRTLoader,
    FacebookChatLoader,
    NotebookLoader,
    CoNLLULoader,
    GoogleApiYoutubeLoader,
    GoogleApiClient,
    CSVLoader,
    # BlackboardLoader
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
