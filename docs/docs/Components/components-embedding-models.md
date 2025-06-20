---
title: Embedding models
slug: /components-embedding-models
---

import Icon from "@site/src/components/icon";

:::important
Components in the **Embedding models** category are moved to **Bundles** as of Langflow 1.5.
Instead, use the [Embedding model](/components-embedding-models#embedding-model) component.
:::

Embedding model components in Langflow generate text embeddings using the selected Large Language Model.

Prior to Langflow 1.5, each embedding model provider had its own component in the **Components** menu and **Playground**.

Most use cases can be performed with the **Language Model** and **Embedding Model** components.

If you want to try additional providers not supported by the new components, the single-provider LLM components of both the **Language Model** and **Embedding Model** types are now found in **Bundles**, and are still available for use.

## Embedding model

Use an **Embedding Model** component in your flow anywhere you would use an embedding model.

Embedding models convert text into numerical vectors. These embeddings capture the semantic meaning of the input text, and allow LLMs to understand context.

This embeddings component uses an OpenAI API key for authentication.

## Use an Embedding Model component in a flow

Create a semantic search system with the **Embedding model** component.

1. Add the **Embedding model** component to your flow.
   The default model is OpenAI's `text-embedding-3-small`. Based on [OpenAI's recommendations](https://platform.openai.com/docs/guides/embeddings#embedding-models), this model is a good balance of performance and cost.
2. In the **OpenAI API Key** field, enter your OpenAI API key.
3. Add a [Split text](/components-processing#split-text) component to your flow.
   This component splits your input text into smaller chunks to be processed into embeddings.
4. Add a [Chroma DB](/components-vector-stores#chroma-db) vector store component to your flow.
   This component stores your text embeddings for later retrieval.
5. Connect the **Text Splitter** component's **Chunks** output to the **Chroma DB** component's **Ingest Data** input.
6. Connect the **Embedding model** component's **Embeddings** output to the **Chroma DB** component's **Embeddings** input.

This flow embeds the split text into the local Chroma vector store using the `text-embedding-3-small` model.
Your flow looks like this:

![Embedding to vector store](/img/component-embedding-models.png)

To query the your vector store, include [Chat Input](/components-io#chat-input) and [Chat Output](/components-io#chat-output) components.

7. Connect a [Chat Input](/components-io#chat-input) component to the **Search Query** input of the Chroma DB vector store.
8. Connect a [Chat Output](/components-io#chat-output) component to the **Search Results** port of the Chroma DB vector store.

Your flow looks like this:
![A simple semantic search flow using Embedding model](/img/component-embedding-models-add-chat.png)

9. Open the **Playground** and enter a search query.
The Playground returns the most semantically similar text chunks.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Type | Description |
|------|--------------|------|-------------|
| provider | Model Provider | Dropdown | Select the embedding model provider. |
| model | Model Name | Dropdown | Select the embedding model to use.|
| api_key | OpenAI API Key | SecretString | The API key required for authenticating with the provider. |
| api_base | API Base URL | String | Base URL for the API. Leave empty for default. |
| dimensions | Dimensions | Integer | The number of dimensions for the output embeddings. |
| chunk_size | Chunk Size | Integer | The size of text chunks to process. Default: `1000`. |
| request_timeout | Request Timeout | Float | Timeout for API requests |
| max_retries | Max Retries | Integer | Maximum number of retry attempts. Default: `3`. |
| show_progress_bar | Show Progress Bar | Boolean | Whether to display a progress bar during embedding generation. |
| model_kwargs | Model Kwargs | Dictionary | Additional keyword arguments to pass to the model. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| embeddings | Embeddings | An instance for generating embeddings using the selected provider. |

</details>

## Embedding models bundles

As of Langflow 1.5, the additional embedding models components are now found under [Bundles](/components-bundle-components) in the components sidebar.

**Bundles** are third-party components grouped by provider.

For more information on bundled components, see the component provider's documentation.



