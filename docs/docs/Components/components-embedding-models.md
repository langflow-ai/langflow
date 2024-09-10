---
title: Embedding Models
sidebar_position: 6
slug: /components-embedding-models
---

# Embedding Models

Embeddings models are used to convert text into numerical vectors. These vectors can be used for various tasks such as similarity search, clustering, and classification.

## AI/ML

This component generates embeddings using the [AI/ML API](https://docs.aimlapi.com/api-overview/embeddings).

### Parameters

#### Inputs

| Name | Type | Description |
|------|------|-------------|
| model_name | String | The name of the AI/ML embedding model to use |
| aiml_api_key | SecretString | API key for authenticating with the AI/ML service |

#### Outputs

| Name | Type | Description |
|------|------|-------------|
| embeddings | Embeddings | An instance of AIMLEmbeddingsImpl for generating embeddings |

## Amazon Bedrock Embeddings

This component is used to load embedding models from [Amazon Bedrock](https://aws.amazon.com/bedrock/).

### Parameters

#### Inputs

| Name | Type | Description |
|------|------|-------------|
| credentials_profile_name | String | Name of the AWS credentials profile in ~/.aws/credentials or ~/.aws/config, which has access keys or role information |
| model_id | String | ID of the model to call, e.g., `amazon.titan-embed-text-v1`. This is equivalent to the `modelId` property in the `list-foundation-models` API |
| endpoint_url | String | URL to set a specific service endpoint other than the default AWS endpoint |
| region_name | String | AWS region to use, e.g., `us-west-2`. Falls back to `AWS_DEFAULT_REGION` environment variable or region specified in ~/.aws/config if not provided |

#### Outputs

| Name | Type | Description |
|------|------|-------------|
| embeddings | Embeddings | An instance for generating embeddings using Amazon Bedrock |


## Astra vectorize

This component is used to generate server-side embeddings using [DataStax Astra](https://docs.datastax.com/en/astra-db-serverless/databases/embedding-generation.html).

### Parameters

#### Inputs

| Name | Type | Description |
|------|------|-------------|
| provider | String | The embedding provider to use |
| model_name | String | The embedding model to use |
| authentication | Dict | Authentication parameters. Use the Astra Portal to add the embedding provider integration to your Astra organization |
| provider_api_key | String | An alternative to the Astra Authentication that lets you use directly the API key of the provider |
| model_parameters | Dict | Additional model parameters |

#### Outputs

| Name | Type | Description |
|------|------|-------------|
| embeddings | Embeddings | An instance for generating embeddings using Astra vectorize |                                                                                      |             |

## Azure OpenAI Embeddings

This component generates embeddings using Azure OpenAI models.

### Parameters

#### Inputs

| Name | Type | Description |
|------|------|-------------|
| Azure Endpoint | String | Your Azure endpoint, including the resource. Example: `https://example-resource.azure.openai.com/` |
| Deployment Name | String | The name of the deployment |
| API Version | String | The API version to use, options include various dates |
| API Key | String | The API key to access the Azure OpenAI service |

#### Outputs

| Name | Type | Description |
|------|------|-------------|
| embeddings | Embeddings | An instance for generating embeddings using Azure OpenAI |

## Cohere Embeddings

This component is used to load embedding models from [Cohere](https://cohere.com/).

### Parameters

#### Inputs

| Name | Type | Description |
|------|------|-------------|
| cohere_api_key | String | API key required to authenticate with the Cohere service |
| model | String | Language model used for embedding text documents and performing queries (default: `embed-english-v2.0`) |
| truncate | Boolean | Whether to truncate the input text to fit within the model's constraints (default: `False`) |

#### Outputs

| Name | Type | Description |
|------|------|-------------|
| embeddings | Embeddings | An instance for generating embeddings using Cohere |

## Hugging Face Inference API Embeddings

This component generates embeddings using Hugging Face Inference API models.

### Parameters

#### Inputs

| Name | Type | Description |
|------|------|-------------|
| API Key | String | API key for accessing the Hugging Face Inference API |
| API URL | String | URL of the Hugging Face Inference API (default: `http://localhost:8080`) |
| Model Name | String | Name of the model to use for embeddings (default: `BAAI/bge-large-en-v1.5`) |
| Cache Folder | String | Folder path to cache Hugging Face models |
| Encode Kwargs | Dict | Additional arguments for the encoding process |
| Model Kwargs | Dict | Additional arguments for the model |
| Multi Process | Boolean | Whether to use multiple processes (default: `False`) |

#### Outputs

| Name | Type | Description |
|------|------|-------------|
| embeddings | Embeddings | An instance for generating embeddings using Hugging Face Inference API |

## MistralAI

This component generates embeddings using MistralAI models.

### Parameters

#### Inputs

| Name | Type | Description |
|------|------|-------------|
| model | String | The MistralAI model to use (default: "mistral-embed") |
| mistral_api_key | SecretString | API key for authenticating with MistralAI |
| max_concurrent_requests | Integer | Maximum number of concurrent API requests (default: 64) |
| max_retries | Integer | Maximum number of retry attempts for failed requests (default: 5) |
| timeout | Integer | Request timeout in seconds (default: 120) |
| endpoint | String | Custom API endpoint URL (default: "https://api.mistral.ai/v1/") |

#### Outputs

| Name | Type | Description |
|------|------|-------------|
| embeddings | Embeddings | MistralAIEmbeddings instance for generating embeddings |

## NVIDIA

This component generates embeddings using NVIDIA models.

### Parameters

#### Inputs

| Name | Type | Description |
|------|------|-------------|
| model | String | The NVIDIA model to use for embeddings (e.g., nvidia/nv-embed-v1) |
| base_url | String | Base URL for the NVIDIA API (default: https://integrate.api.nvidia.com/v1) |
| nvidia_api_key | SecretString | API key for authenticating with NVIDIA's service |
| temperature | Float | Model temperature for embedding generation (default: 0.1) |

#### Outputs

| Name | Type | Description |
|------|------|-------------|
| embeddings | Embeddings | NVIDIAEmbeddings instance for generating embeddings |

## Ollama Embeddings

This component generates embeddings using Ollama models.

### Parameters

#### Inputs

| Name | Type | Description |
|------|------|-------------|
| Ollama Model | String | Name of the Ollama model to use (default: `llama2`) |
| Ollama Base URL | String | Base URL of the Ollama API (default: `http://localhost:11434`) |
| Model Temperature | Float | Temperature parameter for the model. Adjusts the randomness in the generated embeddings |

#### Outputs

| Name | Type | Description |
|------|------|-------------|
| embeddings | Embeddings | An instance for generating embeddings using Ollama |

## OpenAI Embeddings

This component is used to load embedding models from [OpenAI](https://openai.com/).

### Parameters

#### Inputs

| Name | Type | Description |
|------|------|-------------|
| OpenAI API Key | String | The API key to use for accessing the OpenAI API |
| Default Headers | Dict | Default headers for the HTTP requests |
| Default Query | NestedDict | Default query parameters for the HTTP requests |
| Allowed Special | List | Special tokens allowed for processing (default: `[]`) |
| Disallowed Special | List | Special tokens disallowed for processing (default: `["all"]`) |
| Chunk Size | Integer | Chunk size for processing (default: `1000`) |
| Client | Any | HTTP client for making requests |
| Deployment | String | Deployment name for the model (default: `text-embedding-3-small`) |
| Embedding Context Length | Integer | Length of embedding context (default: `8191`) |
| Max Retries | Integer | Maximum number of retries for failed requests (default: `6`) |
| Model | String | Name of the model to use (default: `text-embedding-3-small`) |
| Model Kwargs | NestedDict | Additional keyword arguments for the model |
| OpenAI API Base | String | Base URL of the OpenAI API |
| OpenAI API Type | String | Type of the OpenAI API |
| OpenAI API Version | String | Version of the OpenAI API |
| OpenAI Organization | String | Organization associated with the API key |
| OpenAI Proxy | String | Proxy server for the requests |
| Request Timeout | Float | Timeout for the HTTP requests |
| Show Progress Bar | Boolean | Whether to show a progress bar for processing (default: `False`) |
| Skip Empty | Boolean | Whether to skip empty inputs (default: `False`) |
| TikToken Enable | Boolean | Whether to enable TikToken (default: `True`) |
| TikToken Model Name | String | Name of the TikToken model |

#### Outputs

| Name | Type | Description |
|------|------|-------------|
| embeddings | Embeddings | An instance for generating embeddings using OpenAI |

## VertexAI Embeddings

This component is a wrapper around [Google Vertex AI](https://cloud.google.com/vertex-ai) [Embeddings API](https://cloud.google.com/vertex-ai/docs/generative-ai/embeddings/get-text-embeddings).

### Parameters

#### Inputs

| Name | Type | Description |
|------|------|-------------|
| credentials | Credentials | The default custom credentials to use |
| location | String | The default location to use when making API calls (default: `us-central1`) |
| max_output_tokens | Integer | Token limit determines the maximum amount of text output from one prompt (default: `128`) |
| model_name | String | The name of the Vertex AI large language model (default: `text-bison`) |
| project | String | The default GCP project to use when making Vertex API calls |
| request_parallelism | Integer | The amount of parallelism allowed for requests issued to VertexAI models (default: `5`) |
| temperature | Float | Tunes the degree of randomness in text generations. Should be a non-negative value (default: `0`) |
| top_k | Integer | How the model selects tokens for output, the next token is selected from the top `k` tokens (default: `40`) |
| top_p | Float | Tokens are selected from the most probable to least until the sum of their probabilities exceeds the top `p` value (default: `0.95`) |
| tuned_model_name | String | The name of a tuned model. If provided, `model_name` is ignored |
| verbose | Boolean | This parameter controls the level of detail in the output. When set to `True`, it prints internal states of the chain to help debug (default: `False`) |

#### Outputs

| Name | Type | Description |
|------|------|-------------|
| embeddings | Embeddings | An instance for generating embeddings using VertexAI |

[Previous Vector Stores](/components-vector-stores)

