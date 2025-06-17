<!-- markdownlint-disable MD030 -->

![Langflow logo](./docs/static/img/langflow-logo-color-black-solid.svg)


[![Release Notes](https://img.shields.io/github/release/langflow-ai/langflow?style=flat-square)](https://github.com/langflow-ai/langflow/releases)
[![PyPI - License](https://img.shields.io/badge/license-MIT-orange)](https://opensource.org/licenses/MIT)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/langflow?style=flat-square)](https://pypistats.org/packages/langflow)
[![GitHub star chart](https://img.shields.io/github/stars/langflow-ai/langflow?style=flat-square)](https://star-history.com/#langflow-ai/langflow)
[![Open Issues](https://img.shields.io/github/issues-raw/langflow-ai/langflow?style=flat-square)](https://github.com/langflow-ai/langflow/issues)
[![Twitter](https://img.shields.io/twitter/url/https/twitter.com/langflow-ai.svg?style=social&label=Follow%20%40Langflow)](https://twitter.com/langflow_ai)
[![YouTube Channel](https://img.shields.io/youtube/channel/subscribers/UCn2bInQrjdDYKEEmbpwblLQ?label=Subscribe)](https://www.youtube.com/@Langflow)
[![Discord Server](https://img.shields.io/discord/1116803230643527710?logo=discord&style=social&label=Join)](https://discord.gg/EqksyE2EX9)


[Langflow](https://langflow.org) is a powerful tool for building and deploying AI-powered agents and workflows. It provides developers with both a visual authoring experience and a built-in API server that turns every agent into an API endpoint that can be integrated into applications built on any framework or stack. Langflow comes with batteries included and supports all major LLMs, vector databases and a growing library of AI tools.

## ✨ Highlight features

1. **Visual Builder** to get started quickly and iterate. 
1. **Access to Code** so developers can tweak any component using Python.
1. **Playground** to immediately test and iterate on their flows with step-by-step control.
1. **Multi-agent** orchestration and conversation management and retrieval.
1. **Deploy as an API** or export as JSON for Python apps.
1. **Observability** with LangSmith, LangFuse and other integrations.
1. **Enterprise-ready** security and scalability.

## ⚡️ Quickstart

Langflow works with Python 3.10 to 3.13.

Install with uv **(recommended)** 

```shell
uv pip install langflow
```

Install with pip

```shell
pip install langflow
```

## 📦 Deployment

### Self-managed

Langflow is completely open source and you can deploy it to all major deployment clouds. Follow this [guide](https://docs.langflow.org/deployment-docker) to learn how to use Docker to deploy Langflow.

### Fully-managed by DataStax

DataStax Langflow is a full-managed environment with zero setup. Developers can [sign up for a free account](https://astra.datastax.com/signup?type=langflow) to get started.

## ⭐ Stay up-to-date

Star Langflow on GitHub to be instantly notified of new releases.

![Star Langflow](https://github.com/user-attachments/assets/03168b17-a11d-4b2a-b0f7-c1cce69e5a2c)

## 👋 Contribute

We welcome contributions from developers of all levels. If you'd like to contribute, please check our [contributing guidelines](./CONTRIBUTING.md) and help make Langflow more accessible.

## 📄 Building a Document Analysis System

This guide provides a step-by-step approach to building a document analysis system using Langflow. Such a system can help you extract insights, answer questions, and summarize information from a collection of documents.

### 1. Introduction

A document analysis system allows users to upload or connect a corpus of documents and then interact with that information, typically by asking questions or requesting summaries. These systems leverage Large Language Models (LLMs) and vector databases to understand and search through textual data.

### 2. System Setup

Before you begin, ensure you have the following:

*   **Python**: Langflow supports Python 3.10 to 3.13. Make sure you have a compatible version installed.
*   **Langflow**: Install Langflow using pip or uv:
    ```shell
    uv pip install langflow 
    # or
    pip install langflow
    ```
*   **LLM Access**: You'll need API keys for an LLM provider (e.g., OpenAI, Hugging Face, a local Ollama instance). Configure these within Langflow by navigating to `Settings` > `API Keys` or by setting environment variables.
*   **Vector Database (Optional but Recommended)**: For persistent storage and efficient querying of document embeddings, consider using a vector database like Chroma, Weaviate, or Astra DB. Some can be run locally, while others are cloud-based. Langflow has built-in support for many.

### 3. Core Components & Design Principles

A typical document analysis system involves several key components:

*   **Document Loading**:
    *   **How**: Use Langflow's document loaders (e.g., `PyPDFLoader`, `TextLoader`, `DirectoryLoader`) to ingest documents in various formats (PDF, TXT, DOCX, etc.).
    *   **UX/UI Tip**: Allow users to easily upload single or multiple files, or point to a directory. Provide feedback on successful uploads and loading errors.

*   **Text Processing**:
    *   **Chunking**: Documents are often too large to fit into an LLM's context window. Use text splitters (e.g., `RecursiveCharacterTextSplitter`) to break them into smaller, manageable chunks.
        *   **Design Principle**: Experiment with chunk size and overlap to find what works best for your documents and LLM.
    *   **Embedding**: Convert text chunks into numerical vectors (embeddings) using an embedding model (e.g., from OpenAI, Hugging Face Sentence Transformers). These embeddings capture the semantic meaning of the text.
        *   **Langflow Component**: `OpenAIEmbeddings`, `HuggingFaceEmbeddings`.

*   **Vector Storage & Retrieval**:
    *   **Storage**: Store the embeddings in a vector database for efficient similarity search.
        *   **Langflow Component**: `Chroma`, `FAISS`, `AstraDB`.
    *   **Retrieval**: When a user asks a question, embed the query and search the vector database for the most similar document chunks.
        *   **Design Principle**: The quality of retrieval is crucial. Tune the number of chunks retrieved (`top_k`) to balance context richness and noise.

*   **Question Answering / Information Extraction**:
    *   **LLM Chain**: Pass the retrieved chunks and the user's query to an LLM using a chain (e.g., `RetrievalQA`, `ConversationalRetrievalChain`). The LLM uses the provided context to generate an answer.
        *   **Langflow Component**: `LLMChain`, `RetrievalQA`, `ChatOpenAI`.
    *   **UX/UI Tip**: Clearly display the answer and, if possible, cite the source documents or chunks. Allow for follow-up questions.

*   **User Interface (UI) Design Principles for Great UX**:
    *   **Simplicity**: Keep the interface clean and intuitive. Users should understand how to upload documents and ask questions without a steep learning curve.
    *   **Feedback**: Provide clear feedback at every step (e.g., "Uploading document...", "Processing...", "Generating answer...").
    *   **Clarity**: Display results in an easy-to-read format. Highlight key information and sources.
    *   **Control**: Give users options to customize (e.g., choose different LLMs, adjust retrieval parameters if appropriate for advanced users).
    *   **Error Handling**: Gracefully handle errors (e.g., failed document uploads, LLM API errors) and provide informative messages.

### 4. Langflow Implementation: Building Your Flow

Here's a conceptual outline of a Langflow flow for document analysis:

1.  **Document Input**:
    *   Start with a `DirectoryLoader` or individual file loaders like `PyPDFLoader`.
    *   Connect its output to a `RecursiveCharacterTextSplitter`.

2.  **Embedding and Storage**:
    *   Connect the splitter's output to an embedding component (e.g., `OpenAIEmbeddings`).
    *   Connect the embeddings to a vector store component (e.g., `Chroma`).
        *   *Initial Setup*: When the flow first runs, documents are loaded, chunked, embedded, and stored.
        *   *Subsequent Runs*: The vector store persists the embeddings.

3.  **Querying**:
    *   Use a `TextInput` component for the user's query.
    *   Connect this input and the vector store to a retrieval chain (e.g., `RetrievalQA`).
    *   The `RetrievalQA` chain will also need an LLM component (e.g., `ChatOpenAI`).

4.  **Output**:
    *   Connect the `RetrievalQA` chain's output to a `TextOutput` component or a `ChatOutput` for interactive chat.

**Example Flow (Conceptual):**

```
[DocumentLoader] --> [TextSplitter] --> [EmbeddingModel] --> [VectorStore]
                                                                   ^
                                                                   |
[UserInput (Query)] --> [RetrievalQA (with LLM)] ------------------
                                     |
                                     v
                               [OutputDisplay]
```

*   **Visual Aid**: In Langflow's UI, you would drag these components onto the canvas and connect their outputs to inputs. The lines above represent these connections.

### 5. Best Practices

*   **Modularity**: Build your flow in logical, modular parts. This makes it easier to debug and upgrade components.
*   **Experimentation**:
    *   Test different LLMs, embedding models, and text splitting strategies.
    *   Use Langflow's playground to iterate quickly.
*   **Scalability**: For large document sets or high query volumes, ensure your vector database and LLM setup can scale. Cloud-based managed services can be beneficial.
*   **Cost Management**: Be mindful of API costs for LLMs and embedding models. Implement caching where possible.
*   **Security**: If handling sensitive documents, ensure data is encrypted at rest and in transit. Be cautious about what data is sent to third-party APIs. Consider on-premise or private cloud solutions if necessary.
*   **Evaluation**: Develop a strategy for evaluating the quality of your system's responses. This could involve manual review or automated metrics if applicable.
*   **Iterative Development**: Start simple, get it working, and then add complexity and features based on user feedback.

### 6. Example Use Cases

*   **Research Assistance**: Query a collection of academic papers.
*   **Legal Document Review**: Quickly find relevant clauses or precedents in legal texts.
*   **Customer Support**: Build a knowledge base from support tickets or product documentation to answer common customer questions.
*   **Internal Knowledge Management**: Allow employees to search company policies, reports, and documentation.

By following these steps and principles, you can leverage Langflow to create powerful and user-friendly document analysis systems.

---

[![Star History Chart](https://api.star-history.com/svg?repos=langflow-ai/langflow&type=Timeline)](https://star-history.com/#langflow-ai/langflow&Date)

## ❤️ Contributors

[![langflow contributors](https://contrib.rocks/image?repo=langflow-ai/langflow)](https://github.com/langflow-ai/langflow/graphs/contributors)

