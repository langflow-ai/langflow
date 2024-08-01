---
title: Embedding Models
sidebar_position: 6
slug: /components-embedding-models
---



:::info

This page may contain outdated information. It will be updated as soon as possible.

:::




## Amazon Bedrock Embeddings {#4ddcfde8c1664e358d3f16d718e944d8}


Used to load embedding models from [Amazon Bedrock](https://aws.amazon.com/bedrock/).


| **Parameter**              | **Type** | **Description**                                                                                                                                     | **Default** |
| -------------------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- |
| `credentials_profile_name` | `str`    | Name of the AWS credentials profile in ~/.aws/credentials or ~/.aws/config, which has access keys or role information.                              |             |
| `model_id`                 | `str`    | ID of the model to call, e.g., `amazon.titan-embed-text-v1`. This is equivalent to the `modelId` property in the `list-foundation-models` API.      |             |
| `endpoint_url`             | `str`    | URL to set a specific service endpoint other than the default AWS endpoint.                                                                         |             |
| `region_name`              | `str`    | AWS region to use, e.g., `us-west-2`. Falls back to `AWS_DEFAULT_REGION` environment variable or region specified in ~/.aws/config if not provided. |             |


## Astra vectorize {#c1e6d1373824424ea130e052ba0f46af}


Used to generate server-side embeddings using [DataStax Astra](https://docs.datastax.com/en/astra-db-serverless/databases/embedding-generation.html).


| **Parameter**      | **Type** | **Description**                                                                                                       | **Default** |
| ------------------ | -------- | --------------------------------------------------------------------------------------------------------------------- | ----------- |
| `provider`         | `str`    | The embedding provider to use.                                                                                        |             |
| `model_name`       | `str`    | The embedding model to use.                                                                                           |             |
| `authentication`   | `dict`   | Authentication parameters. Use the Astra Portal to add the embedding provider integration to your Astra organization. |             |
| `provider_api_key` | `str`    | An alternative to the Astra Authentication that let you use directly the API key of the provider.                     |             |
| `model_parameters` | `dict`   | Additional model parameters.                                                                                          |             |


## Cohere Embeddings {#0c5b7b8790da448fabd4c5ddba1fcbde}


Used to load embedding models from [Cohere](https://cohere.com/).


| **Parameter**    | **Type** | **Description**                                                           | **Default**          |
| ---------------- | -------- | ------------------------------------------------------------------------- | -------------------- |
| `cohere_api_key` | `str`    | API key required to authenticate with the Cohere service.                 |                      |
| `model`          | `str`    | Language model used for embedding text documents and performing queries.  | `embed-english-v2.0` |
| `truncate`       | `bool`   | Whether to truncate the input text to fit within the model's constraints. | `False`              |


## Azure OpenAI Embeddings {#8ffb790d5a6c484dab3fe6c777638a44}


Generate embeddings using Azure OpenAI models.


| **Parameter**     | **Type** | **Description**                                                                                    | **Default** |
| ----------------- | -------- | -------------------------------------------------------------------------------------------------- | ----------- |
| `Azure Endpoint`  | `str`    | Your Azure endpoint, including the resource. Example: `https://example-resource.azure.openai.com/` |             |
| `Deployment Name` | `str`    | The name of the deployment.                                                                        |             |
| `API Version`     | `str`    | The API version to use, options include various dates.                                             |             |
| `API Key`         | `str`    | The API key to access the Azure OpenAI service.                                                    |             |


## Hugging Face API Embeddings {#8536e4ee907b48688e603ae9bf7822cb}


Generate embeddings using Hugging Face Inference API models.


| **Parameter**   | **Type** | **Description**                                       | **Default**              |
| --------------- | -------- | ----------------------------------------------------- | ------------------------ |
| `API Key`       | `str`    | API key for accessing the Hugging Face Inference API. |                          |
| `API URL`       | `str`    | URL of the Hugging Face Inference API.                | `http://localhost:8080`  |
| `Model Name`    | `str`    | Name of the model to use for embeddings.              | `BAAI/bge-large-en-v1.5` |
| `Cache Folder`  | `str`    | Folder path to cache Hugging Face models.             |                          |
| `Encode Kwargs` | `dict`   | Additional arguments for the encoding process.        |                          |
| `Model Kwargs`  | `dict`   | Additional arguments for the model.                   |                          |
| `Multi Process` | `bool`   | Whether to use multiple processes.                    | `False`                  |


## Hugging Face Embeddings {#b2b74732874743d3be6fdf8aae049e74}


Used to load embedding models from [HuggingFace](https://huggingface.co/).


| **Parameter**   | **Type** | **Description**                                | **Default**                               |
| --------------- | -------- | ---------------------------------------------- | ----------------------------------------- |
| `Cache Folder`  | `str`    | Folder path to cache HuggingFace models.       |                                           |
| `Encode Kwargs` | `dict`   | Additional arguments for the encoding process. |                                           |
| `Model Kwargs`  | `dict`   | Additional arguments for the model.            |                                           |
| `Model Name`    | `str`    | Name of the HuggingFace model to use.          | `sentence-transformers/all-mpnet-base-v2` |
| `Multi Process` | `bool`   | Whether to use multiple processes.             | `False`                                   |


## OpenAI Embeddings {#af7630df05a245d1a632e1bf6db2a4c5}


Used to load embedding models from [OpenAI](https://openai.com/).


| **Parameter**              | **Type**         | **Description**                                  | **Default**              |
| -------------------------- | ---------------- | ------------------------------------------------ | ------------------------ |
| `OpenAI API Key`           | `str`            | The API key to use for accessing the OpenAI API. |                          |
| `Default Headers`          | `Dict[str, str]` | Default headers for the HTTP requests.           |                          |
| `Default Query`            | `NestedDict`     | Default query parameters for the HTTP requests.  |                          |
| `Allowed Special`          | `List[str]`      | Special tokens allowed for processing.           | `[]`                     |
| `Disallowed Special`       | `List[str]`      | Special tokens disallowed for processing.        | `["all"]`                |
| `Chunk Size`               | `int`            | Chunk size for processing.                       | `1000`                   |
| `Client`                   | `Any`            | HTTP client for making requests.                 |                          |
| `Deployment`               | `str`            | Deployment name for the model.                   | `text-embedding-3-small` |
| `Embedding Context Length` | `int`            | Length of embedding context.                     | `8191`                   |
| `Max Retries`              | `int`            | Maximum number of retries for failed requests.   | `6`                      |
| `Model`                    | `str`            | Name of the model to use.                        | `text-embedding-3-small` |
| `Model Kwargs`             | `NestedDict`     | Additional keyword arguments for the model.      |                          |
| `OpenAI API Base`          | `str`            | Base URL of the OpenAI API.                      |                          |
| `OpenAI API Type`          | `str`            | Type of the OpenAI API.                          |                          |
| `OpenAI API Version`       | `str`            | Version of the OpenAI API.                       |                          |
| `OpenAI Organization`      | `str`            | Organization associated with the API key.        |                          |
| `OpenAI Proxy`             | `str`            | Proxy server for the requests.                   |                          |
| `Request Timeout`          | `float`          | Timeout for the HTTP requests.                   |                          |
| `Show Progress Bar`        | `bool`           | Whether to show a progress bar for processing.   | `False`                  |
| `Skip Empty`               | `bool`           | Whether to skip empty inputs.                    | `False`                  |
| `TikToken Enable`          | `bool`           | Whether to enable TikToken.                      | `True`                   |
| `TikToken Model Name`      | `str`            | Name of the TikToken model.                      |                          |


## Ollama Embeddings {#a26d2cb92e6d44669c2cfff71a5e9431}


Generate embeddings using Ollama models.


| **Parameter**       | **Type** | **Description**                                                                          | **Default**              |
| ------------------- | -------- | ---------------------------------------------------------------------------------------- | ------------------------ |
| `Ollama Model`      | `str`    | Name of the Ollama model to use.                                                         | `llama2`                 |
| `Ollama Base URL`   | `str`    | Base URL of the Ollama API.                                                              | `http://localhost:11434` |
| `Model Temperature` | `float`  | Temperature parameter for the model. Adjusts the randomness in the generated embeddings. |                          |


## VertexAI Embeddings {#707b38c23cb9413fbbaab1ae7b872311}


Wrapper around [Google Vertex AI](https://cloud.google.com/vertex-ai) [Embeddings API](https://cloud.google.com/vertex-ai/docs/generative-ai/embeddings/get-text-embeddings).


| **Parameter**         | **Type**      | **Description**                                                                                                                      | **Default**   |
| --------------------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ------------- |
| `credentials`         | `Credentials` | The default custom credentials to use.                                                                                               |               |
| `location`            | `str`         | The default location to use when making API calls.                                                                                   | `us-central1` |
| `max_output_tokens`   | `int`         | Token limit determines the maximum amount of text output from one prompt.                                                            | `128`         |
| `model_name`          | `str`         | The name of the Vertex AI large language model.                                                                                      | `text-bison`  |
| `project`             | `str`         | The default GCP project to use when making Vertex API calls.                                                                         |               |
| `request_parallelism` | `int`         | The amount of parallelism allowed for requests issued to VertexAI models.                                                            | `5`           |
| `temperature`         | `float`       | Tunes the degree of randomness in text generations. Should be a non-negative value.                                                  | `0`           |
| `top_k`               | `int`         | How the model selects tokens for output, the next token is selected from the top `k` tokens.                                         | `40`          |
| `top_p`               | `float`       | Tokens are selected from the most probable to least until the sum of their probabilities exceeds the top `p` value.                  | `0.95`        |
| `tuned_model_name`    | `str`         | The name of a tuned model. If provided, `model_name` is ignored.                                                                     |               |
| `verbose`             | `bool`        | This parameter controls the level of detail in the output. When set to `True`, it prints internal states of the chain to help debug. | `False`       |


[Previous Vector Stores](/components-vector-stores)

