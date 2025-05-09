---
title: Embeddings
slug: /components-embedding-models
---

import Icon from "@site/src/components/icon";

# Embeddings models in Langflow

Embeddings models convert text into numerical vectors. These embeddings capture the semantic meaning of the input text, and allow LLMs to understand context.

Refer to your specific component's documentation for more information on parameters.

## Use an embeddings model component in a flow

In this example of a document ingestion pipeline, the **OpenAI** embeddings model is connected to a vector database. The component converts the text chunks into vectors and stores them in the vector database. The vectorized data can be used to inform AI workloads like chatbots, similarity searches, and agents.

This embeddings component uses an OpenAI API key for authentication. Refer to your specific embeddings component's documentation for more information on authentication.

![URL component in a data ingestion pipeline](/img/url-component.png)

## AI/ML

This component generates embeddings using the [AI/ML API](https://docs.aimlapi.com/api-overview/embeddings).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| model_name | String | The name of the AI/ML embedding model to use. |
| aiml_api_key | SecretString | The API key required for authenticating with the AI/ML service. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| embeddings | Embeddings | An instance of `AIMLEmbeddingsImpl` for generating embeddings. |

</details>

## Amazon Bedrock Embeddings

This component is used to load embedding models from [Amazon Bedrock](https://aws.amazon.com/bedrock/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| credentials_profile_name | String | The name of the AWS credentials profile in `~/.aws/credentials` or `~/.aws/config`, which has access keys or role information. |
| model_id | String | The ID of the model to call, such as `amazon.titan-embed-text-v1`. This is equivalent to the `modelId` property in the `list-foundation-models` API. |
| endpoint_url | String | The URL to set a specific service endpoint other than the default AWS endpoint. |
| region_name | String | The AWS region to use, such as `us-west-2`. Falls back to the `AWS_DEFAULT_REGION` environment variable or region specified in `~/.aws/config` if not provided. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| embeddings | Embeddings | An instance for generating embeddings using Amazon Bedrock. |

</details>

## Astra DB vectorize

:::important
This component is deprecated as of Langflow version 1.1.2.
Instead, use the [Astra DB vector store component](/components-vector-stores#astra-db-vector-store).
:::

Connect this component to the **Embeddings** port of the [Astra DB vector store component](/components-vector-stores#astra-db-vector-store) to generate embeddings.

This component requires that your Astra DB database has a collection that uses a vectorize embedding provider integration.
For more information and instructions, see [Embedding Generation](https://docs.datastax.com/en/astra-db-serverless/databases/embedding-generation.html).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| provider | Embedding Provider | The embedding provider to use. |
| model_name | Model Name | The embedding model to use. |
| authentication | Authentication | The name of the API key in Astra that stores your [vectorize embedding provider credentials](https://docs.datastax.com/en/astra-db-serverless/databases/embedding-generation.html#embedding-provider-authentication). (Not required if using an [Astra-hosted embedding provider](https://docs.datastax.com/en/astra-db-serverless/databases/embedding-generation.html#supported-embedding-providers).) |
| provider_api_key | Provider API Key | As an alternative to `authentication`, directly provide your embedding provider credentials. |
| model_parameters | Model Parameters | Additional model parameters. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| embeddings | Embeddings | An instance for generating embeddings using Astra vectorize. |

</details>

## Azure OpenAI Embeddings

This component generates embeddings using Azure OpenAI models.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| Model | String | The name of the model to use. Default: `text-embedding-3-small`. |
| Azure Endpoint | String | Your Azure endpoint, including the resource, such as `https://example-resource.azure.openai.com/`. |
| Deployment Name | String | The name of the deployment. |
| API Version | String | The API version to use, with options including various dates. |
| API Key | String | The API key required to access the Azure OpenAI service. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| embeddings | Embeddings | An instance for generating embeddings using Azure OpenAI. |

</details>

## Cloudflare Workers AI Embeddings

This component generates embeddings using [Cloudflare Workers AI models](https://developers.cloudflare.com/workers-ai/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| account_id | Cloudflare account ID | [Find your Cloudflare account ID](https://developers.cloudflare.com/fundamentals/setup/find-account-and-zone-ids/#find-account-id-workers-and-pages). |
| api_token | Cloudflare API token | [Create an API token](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/). |
| model_name | Model Name | [List of supported models](https://developers.cloudflare.com/workers-ai/models/#text-embeddings). |
| strip_new_lines | Strip New Lines | Whether to strip new lines from the input text. |
| batch_size | Batch Size | The number of texts to embed in each batch. |
| api_base_url | Cloudflare API base URL | The base URL for the Cloudflare API. |
| headers | Headers | Additional request headers. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| embeddings | Embeddings | An instance for generating embeddings using Cloudflare Workers. |

</details>

## Cohere Embeddings

This component is used to load embedding models from [Cohere](https://cohere.com/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| cohere_api_key | String | The API key required to authenticate with the Cohere service. |
| model | String | The language model used for embedding text documents and performing queries. Default: `embed-english-v2.0`. |
| truncate | Boolean | Whether to truncate the input text to fit within the model's constraints. Default: `False`. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| embeddings | Embeddings | An instance for generating embeddings using Cohere. |

</details>

## Embedding similarity

This component computes selected forms of similarity between two embedding vectors.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| embedding_vectors | Embedding Vectors | A list containing exactly two data objects with embedding vectors to compare. |
| similarity_metric | Similarity Metric | Select the similarity metric to use. Options: "Cosine Similarity", "Euclidean Distance", "Manhattan Distance". |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| similarity_data | Similarity Data | A data object containing the computed similarity score and additional information. |

</details>

## Google generative AI embeddings

This component connects to Google's generative AI embedding service using the GoogleGenerativeAIEmbeddings class from the `langchain-google-genai` package.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| api_key | API Key | The secret API key for accessing Google's generative AI service. Required. |
| model_name | Model Name | The name of the embedding model to use. Default: "models/text-embedding-004". |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| embeddings | Embeddings | The built GoogleGenerativeAIEmbeddings object. |

</details>

## Hugging Face Embeddings

:::note
This component is deprecated as of Langflow version 1.0.18.
Instead, use the [Hugging Face Embeddings Inference component](#hugging-face-embeddings-inference).
:::

This component loads embedding models from HuggingFace.

Use this component to generate embeddings using locally downloaded Hugging Face models. Ensure you have sufficient computational resources to run the models.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| Cache Folder | Cache Folder | The folder path to cache HuggingFace models. |
| Encode Kwargs | Encoding Arguments | Additional arguments for the encoding process. |
| Model Kwargs | Model Arguments | Additional arguments for the model. |
| Model Name | Model Name | The name of the HuggingFace model to use. |
| Multi Process | Multi-Process | Whether to use multiple processes. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| embeddings | Embeddings | The generated embeddings. |

</details>

## Hugging Face embeddings inference

This component generates embeddings using [Hugging Face Inference API models](https://huggingface.co/) and requires a [Hugging Face API token](https://huggingface.co/docs/hub/security-tokens) to authenticate. Local inference models do not require an API key.

Use this component to create embeddings with Hugging Face's hosted models, or to connect to your own locally hosted models.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| API Key | API Key | The API key for accessing the Hugging Face Inference API. |
| API URL | API URL | The URL of the Hugging Face Inference API. |
| Model Name | Model Name | The name of the model to use for embeddings. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| embeddings | Embeddings | The generated embeddings. |

</details>

### Connect the Hugging Face component to a local embeddings model

To run an embeddings inference locally, see the [HuggingFace documentation](https://huggingface.co/docs/text-embeddings-inference/local_cpu).

To connect the local Hugging Face model to the **Hugging Face embeddings inference** component and use it in a flow, follow these steps:

1. Create a [Vector store RAG flow](/starter-projects-vector-store-rag).
There are two embeddings models in this flow that you can replace with **Hugging Face** embeddings inference components.
2. Replace both **OpenAI** embeddings model components with **Hugging Face** model components.
3. Connect both **Hugging Face** components to the **Embeddings** ports of the **Astra DB vector store** components.
4. In the **Hugging Face** components, set the **Inference Endpoint** field to the URL of your local inference model. **The **API Key** field is not required for local inference.**
5. Run the flow. The local inference models generate embeddings for the input text.

## IBM watsonx embeddings

This component generates text using [IBM watsonx.ai](https://www.ibm.com/watsonx) foundation models.

To use **IBM watsonx.ai** embeddings components, replace an embeddings component with the IBM watsonx.ai component in a flow.

An example document processing flow looks like the following:

![IBM watsonx embeddings model loading a chroma-db with split text](/img/component-watsonx-embeddings-chroma.png)

This flow loads a PDF file from local storage and splits the text into chunks.

The **IBM watsonx** embeddings component converts the text chunks into embeddings, which are then stored in a Chroma DB vector store.

The values for **API endpoint**, **Project ID**, **API key**, and **Model Name** are found in your IBM watsonx.ai deployment.
For more information, see the [Langchain documentation](https://python.langchain.com/docs/integrations/text_embedding/ibm_watsonx/).

### Default models

The component supports several default models with the following vector dimensions:

- `sentence-transformers/all-minilm-l12-v2`: 384-dimensional embeddings
- `ibm/slate-125m-english-rtrvr-v2`: 768-dimensional embeddings
- `ibm/slate-30m-english-rtrvr-v2`: 768-dimensional embeddings
- `intfloat/multilingual-e5-large`: 1024-dimensional embeddings

The component automatically fetches and updates the list of available models from your watsonx.ai instance when you provide your API endpoint and credentials.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| url | watsonx API Endpoint | The base URL of the API. |
| project_id | watsonx project id | The project ID for your watsonx.ai instance. |
| api_key | API Key | The API Key to use for the model. |
| model_name | Model Name | The name of the embedding model to use. |
| truncate_input_tokens | Truncate Input Tokens | The maximum number of tokens to process. Default: `200`. |
| input_text | Include the original text in the output | Determines if the original text is included in the output. Default: `True`. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| embeddings | Embeddings | An instance for generating embeddings using watsonx.ai. |

</details>

## LM Studio Embeddings

This component generates embeddings using [LM Studio](https://lmstudio.ai/docs) models.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| model | Model | The LM Studio model to use for generating embeddings. |
| base_url | LM Studio Base URL | The base URL for the LM Studio API. |
| api_key | LM Studio API Key | The API key for authentication with LM Studio. |
| temperature | Model Temperature | The temperature setting for the model. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| embeddings | Embeddings | The generated embeddings. |

</details>

## MistralAI

This component generates embeddings using [MistralAI](https://docs.mistral.ai/) models.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| model | String | The MistralAI model to use. Default: "mistral-embed". |
| mistral_api_key | SecretString | The API key for authenticating with MistralAI. |
| max_concurrent_requests | Integer | The maximum number of concurrent API requests. Default: 64. |
| max_retries | Integer | The maximum number of retry attempts for failed requests. Default: 5. |
| timeout | Integer | The request timeout in seconds. Default: 120. |
| endpoint | String | The custom API endpoint URL. Default: `https://api.mistral.ai/v1/`). |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| embeddings | Embeddings | A MistralAIEmbeddings instance for generating embeddings. |

</details>

## NVIDIA

This component generates embeddings using [NVIDIA models](https://docs.nvidia.com).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| model | String | The NVIDIA model to use for embeddings, such as `nvidia/nv-embed-v1`. |
| base_url | String | The base URL for the NVIDIA API. Default: `https://integrate.api.nvidia.com/v1`. |
| nvidia_api_key | SecretString | The API key for authenticating with NVIDIA's service. |
| temperature | Float | The model temperature for embedding generation. Default: `0.1`. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| embeddings | Embeddings | A NVIDIAEmbeddings instance for generating embeddings. |

</details>

## Ollama embeddings

This component generates embeddings using [Ollama models](https://ollama.com/).

For a list of Ollama embeddings models, see the [Ollama documentation](https://ollama.com/search?c=embedding).

To use this component in a flow, connect Langflow to your locally running Ollama server and select an embeddings model.

1. In the Ollama component, in the **Ollama Base URL** field, enter the address for your locally running Ollama server.
This value is set as the `OLLAMA_HOST` environment variable in Ollama. The default base URL is `http://127.0.0.1:11434`.
2. To refresh the server's list of models, click <Icon name="RefreshCw" aria-label="Refresh"/>.
3. In the **Ollama Model** field, select an embeddings model. This example uses `all-minilm:latest`.
4. Connect the **Ollama** embeddings component to a flow.
For example, this flow connects a local Ollama server running a `all-minilm:latest` embeddings model to a [Chroma DB](/components-vector-stores#chroma-db) vector store to generate embeddings for split text.

![Ollama embeddings connected to Chroma DB](/img/component-ollama-embeddings-chromadb.png)

For more information, see the [Ollama documentation](https://ollama.com/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| Ollama Model | String | The name of the Ollama model to use. Default: `llama2`. |
| Ollama Base URL | String | The base URL of the Ollama API. Default: `http://localhost:11434`. |
| Model Temperature | Float | The temperature parameter for the model. Adjusts the randomness in the generated embeddings. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| embeddings | Embeddings | An instance for generating embeddings using Ollama. |

</details>

## OpenAI Embeddings

This component is used to load embedding models from [OpenAI](https://openai.com/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| OpenAI API Key | String | The API key to use for accessing the OpenAI API. |
| Default Headers | Dict | The default headers for the HTTP requests. |
| Default Query | NestedDict | The default query parameters for the HTTP requests. |
| Allowed Special | List | The special tokens allowed for processing. Default: `[]`. |
| Disallowed Special | List | The special tokens disallowed for processing. Default: `["all"]`. |
| Chunk Size | Integer | The chunk size for processing. Default: `1000`. |
| Client | Any | The HTTP client for making requests. |
| Deployment | String | The deployment name for the model. Default: `text-embedding-3-small`. |
| Embedding Context Length | Integer | The length of embedding context. Default: `8191`. |
| Max Retries | Integer | The maximum number of retries for failed requests. Default: `6`. |
| Model | String | The name of the model to use. Default: `text-embedding-3-small`. |
| Model Kwargs | NestedDict | Additional keyword arguments for the model. |
| OpenAI API Base | String | The base URL of the OpenAI API. |
| OpenAI API Type | String | The type of the OpenAI API. |
| OpenAI API Version | String | The version of the OpenAI API. |
| OpenAI Organization | String | The organization associated with the API key. |
| OpenAI Proxy | String | The proxy server for the requests. |
| Request Timeout | Float | The timeout for the HTTP requests. |
| Show Progress Bar | Boolean | Whether to show a progress bar for processing. Default: `False`. |
| Skip Empty | Boolean | Whether to skip empty inputs. Default: `False`. |
| TikToken Enable | Boolean | Whether to enable TikToken. Default: `True`. |
| TikToken Model Name | String | The name of the TikToken model. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| embeddings | Embeddings | An instance for generating embeddings using OpenAI. |

</details>

## Text embedder

This component generates embeddings for a given message using a specified embedding model.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| embedding_model | Embedding Model | The embedding model to use for generating embeddings. |
| message | Message | The message for which to generate embeddings. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| embeddings | Embedding Data | A data object containing the original text and its embedding vector. |

</details>

## VertexAI Embeddings

This component is a wrapper around [Google Vertex AI](https://cloud.google.com/vertex-ai) [Embeddings API](https://cloud.google.com/vertex-ai/docs/generative-ai/embeddings/get-text-embeddings).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| credentials | Credentials | The default custom credentials to use. |
| location | String | The default location to use when making API calls. Default: `us-central1`. |
| max_output_tokens | Integer | The token limit determines the maximum amount of text output from one prompt. Default: `128`. |
| model_name | String | The name of the Vertex AI large language model. Default: `text-bison`. |
| project | String | The default GCP project to use when making Vertex API calls. |
| request_parallelism | Integer | The amount of parallelism allowed for requests issued to VertexAI models. Default: `5`. |
| temperature | Float | Tunes the degree of randomness in text generations. Should be a non-negative value. Default: `0`. |
| top_k | Integer | How the model selects tokens for output. The next token is selected from the top `k` tokens. Default: `40`. |
| top_p | Float | Tokens are selected from the most probable to least until the sum of their probabilities exceeds the top `p` value. Default: `0.95`. |
| tuned_model_name | String | The name of a tuned model. If provided, `model_name` is ignored. |
| verbose | Boolean | This parameter controls the level of detail in the output. When set to `True`, it prints internal states of the chain to help debug. Default: `False`. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| embeddings | Embeddings | An instance for generating embeddings using VertexAI. |

</details>

