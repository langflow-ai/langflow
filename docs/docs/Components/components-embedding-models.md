---
title: Embedding models
slug: /components-embedding-models
---

import Icon from "@site/src/components/icon";

:::important
In [Langflow version 1.5](/release-notes), the singular **Embedding model** component replaces many provider-specific embedding models components. Any provider-specific embedding model components that weren't incorporated into the singular component were moved to [**Bundles**](/components-bundle-components).
:::

Embedding model components in Langflow generate text embeddings using the selected Large Language Model (LLM). The core **Embedding model** component supports many LLM providers, models, and use cases. For additional providers and models not supported by the core **Embedding model** component, see [Bundles](/components-bundle-components).

The core **Language Model** and **Embedding Model** components are adequate for most use cases.


## Use an Embedding Model component in a flow

Create a semantic search system with the **Embedding model** component.

1. Add the **Embedding model** component to your flow.
   The default model is OpenAI's `text-embedding-3-small`, which is a balanced model, based on [OpenAI's recommendations](https://platform.openai.com/docs/guides/embeddings#embedding-models).
2. In the **OpenAI API Key** field, enter your OpenAI API key.
3. Add a [Split text](/components-processing#split-text) component to your flow.
   This component splits your input text into smaller chunks to be processed into embeddings.
4. Add a [Chroma DB](/components-vector-stores#chroma-db) vector store component to your flow.
   This component stores your text embeddings for later retrieval.
5. Connect the **Text Splitter** component's **Chunks** output to the **Chroma DB** component's **Ingest Data** input.
6. Connect the **Embedding model** component's **Embeddings** output to the **Chroma DB** component's **Embeddings** input.

This flow loads a file from the File loader, splits the text, and embeds the split text into the local Chroma vector store using the `text-embedding-3-small` model.

![Embeddings connected to Chroma DB vector store with a file loader and a split text component](/img/component-embedding-models.png)

To query the vector store, include [Chat Input](/components-io#chat-input) and [Chat Output](/components-io#chat-output) components.

7. Connect a [Chat Input](/components-io#chat-input) component to the **Search Query** input of the Chroma DB vector store.
8. Connect a [Chat Output](/components-io#chat-output) component to the **Search Results** port of the Chroma DB vector store.

Your flow looks like the following:
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

If your provider or model isn't supported by the core **Embedding model** component, see [Bundles](/components-bundle-components) for additional language model and embedding model components developed by third-party contributors.