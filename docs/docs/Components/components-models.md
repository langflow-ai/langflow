---
title: Models
sidebar_position: 5
slug: /components-models
---

# Models

Model components are used to generate text using language models. These components can be used to generate text for various tasks such as chatbots, content generation, and more.

## AI/ML API

This component creates a ChatOpenAI model instance using the AIML API.

For more information, see [AIML documentation](https://docs.aimlapi.com/).

### Parameters

#### Inputs

| Name         | Type        | Description                                                                                 |
|--------------|-------------|---------------------------------------------------------------------------------------------|
| max_tokens   | Integer     | The maximum number of tokens to generate. Set to 0 for unlimited tokens. Range: 0-128000. |
| model_kwargs | Dictionary | Additional keyword arguments for the model.                                                |
| model_name   | String      | The name of the AIML model to use. Options are predefined in AIML_CHAT_MODELS.              |
| aiml_api_base| String      | The base URL of the AIML API. Defaults to https://api.aimlapi.com.                          |
| api_key      | SecretString| The AIML API Key to use for the model.                                                       |
| temperature  | Float       | Controls randomness in the output. Default: 0.1.                                            |
| seed         | Integer     | Controls reproducibility of the job.                                                         |

#### Outputs

| Name  | Type          | Description                                                      |
|-------|---------------|------------------------------------------------------------------|
| model | LanguageModel | An instance of ChatOpenAI configured with the specified parameters. |

## Amazon Bedrock

This component generates text using Amazon Bedrock LLMs.

For more information, see [Amazon Bedrock documentation](https://docs.aws.amazon.com/bedrock).

### Parameters

#### Inputs

| Name                   | Type         | Description                                                                         |
|------------------------|--------------|-------------------------------------------------------------------------------------|
| model_id               | String       | The ID of the Amazon Bedrock model to use. Options include various models.         |
| aws_access_key         | SecretString | AWS Access Key for authentication.                                                   |
| aws_secret_key         | SecretString | AWS Secret Key for authentication.                                                   |
| credentials_profile_name | String    | Name of the AWS credentials profile to use (advanced).                              |
| region_name            | String       | AWS region name. Default: "us-east-1".                                               |
| model_kwargs           | Dictionary   | Additional keyword arguments for the model (advanced).                               |
| endpoint_url           | String       | Custom endpoint URL for the Bedrock service (advanced).                              |

#### Outputs

| Name  | Type          | Description                                                       |
|-------|---------------|-------------------------------------------------------------------|
| model | LanguageModel | An instance of ChatBedrock configured with the specified parameters. |

## Anthropic

This component allows the generation of text using Anthropic Chat and Language models.

For more information, see the [Anthropic documentation](https://docs.anthropic.com/en/docs/welcome).

### Parameters

#### Inputs

| Name                | Type        | Description                                                                            |
|---------------------|-------------|----------------------------------------------------------------------------------------|
| max_tokens          | Integer     | The maximum number of tokens to generate. Set to 0 for unlimited tokens. Default: 4096.|
| model               | String      | The name of the Anthropic model to use. Options include various Claude 3 models.      |
| anthropic_api_key   | SecretString| Your Anthropic API key for authentication.                                              |
| temperature         | Float       | Controls randomness in the output. Default: 0.1.                                       |
| anthropic_api_url   | String      | Endpoint of the Anthropic API. Defaults to 'https://api.anthropic.com' if not specified (advanced). |
| prefill             | String      | Prefill text to guide the model's response (advanced).                                 |

#### Outputs

| Name  | Type          | Description                                                      |
|-------|---------------|------------------------------------------------------------------|
| model | LanguageModel | An instance of ChatAnthropic configured with the specified parameters. |

## Azure OpenAI

This component generates text using Azure OpenAI LLM.

For more information, see the [Azure OpenAI documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/).

### Parameters

#### Inputs

| Name                | Display Name       | Info                                                                            |
|---------------------|---------------------|---------------------------------------------------------------------------------|
| Model Name          | Model Name          | Specifies the name of the Azure OpenAI model to be used for text generation.    |
| Azure Endpoint      | Azure Endpoint      | Your Azure endpoint, including the resource.                                    |
| Deployment Name     | Deployment Name     | Specifies the name of the deployment.                                           |
| API Version         | API Version         | Specifies the version of the Azure OpenAI API to be used.                        |
| API Key             | API Key             | Your Azure OpenAI API key.                                                       |
| Temperature         | Temperature         | Specifies the sampling temperature. Defaults to `0.7`.                           |
| Max Tokens          | Max Tokens          | Specifies the maximum number of tokens to generate. Defaults to `1000`.         |
| Input Value         | Input Value         | Specifies the input text for text generation.                                    |
| Stream              | Stream              | Specifies whether to stream the response from the model. Defaults to `False`.    |

## Cohere

This component generates text using Cohere's language models.

For more information, see the [Cohere documentation](https://cohere.ai/).

### Parameters

#### Inputs

| Name                | Display Name      | Info                                                     |
|---------------------|--------------------|----------------------------------------------------------|
| Cohere API Key      | Cohere API Key     | Your Cohere API key.                                    |
| Max Tokens          | Max Tokens         | Specifies the maximum number of tokens to generate. Defaults to `256`. |
| Temperature         | Temperature        | Specifies the sampling temperature. Defaults to `0.75`. |
| Input Value         | Input Value        | Specifies the input text for text generation.           |

## Google Generative AI

This component generates text using Google's Generative AI models.

For more information, see the [Google Generative AI documentation](https://cloud.google.com/ai-platform/training/docs/algorithms/gpt-3).

### Parameters

#### Inputs

| Name                | Display Name      | Info                                                                  |
|---------------------|--------------------|-----------------------------------------------------------------------|
| Google API Key      | Google API Key     | Your Google API key to use for the Google Generative AI.              |
| Model               | Model              | The name of the model to use, such as `"gemini-pro"`.                 |
| Max Output Tokens   | Max Output Tokens  | The maximum number of tokens to generate.                             |
| Temperature         | Temperature        | Run inference with this temperature.                                  |
| Top K               | Top K              | Consider the set of top K most probable tokens.                       |
| Top P               | Top P              | The maximum cumulative probability of tokens to consider when sampling. |
| N                   | N                  | Number of chat completions to generate for each prompt.                |

## Groq

This component generates text using Groq's language models.

For more information, see the [Groq documentation](https://groq.com/).

### Parameters

#### Inputs

| Name           | Type          | Description                                                     |
|----------------|---------------|-----------------------------------------------------------------|
| groq_api_key    | SecretString   | API key for the Groq API.                                      |
| groq_api_base   | String         | Base URL path for API requests. Default: "https://api.groq.com" (advanced). |
| max_tokens      | Integer        | The maximum number of tokens to generate (advanced).           |
| temperature     | Float          | Controls randomness in the output. Range: [0.0, 1.0]. Default: 0.1. |
| n               | Integer        | Number of chat completions to generate for each prompt (advanced). |
| model_name      | String         | The name of the Groq model to use. Options are dynamically fetched from the Groq API. |

#### Outputs

| Name  | Type          | Description                                                      |
|-------|---------------|------------------------------------------------------------------|
| model | LanguageModel | An instance of ChatGroq configured with the specified parameters. |

## Hugging Face API

This component generates text using Hugging Face's language models.

For more information, see the [Hugging Face documentation](https://huggingface.co/).

### Parameters

#### Inputs

| Name                | Display Name     | Info                                      |
|---------------------|-------------------|-------------------------------------------|
| Endpoint URL        | Endpoint URL      | The URL of the Hugging Face Inference API endpoint. |
| Task                | Task              | Specifies the task for text generation.   |
| API Token           | API Token         | The API token required for authentication.|
| Model Kwargs        | Model Kwargs      | Additional keyword arguments for the model.|
| Input Value         | Input Value       | The input text for text generation.       |

## Maritalk

This component generates text using Maritalk LLMs.

For more information, see [Maritalk documentation](https://www.maritalk.com/).

### Parameters

#### Inputs

| Name           | Type          | Description                                                     |
|----------------|---------------|-----------------------------------------------------------------|
| max_tokens      | Integer        | The maximum number of tokens to generate. Set to 0 for unlimited tokens. Default: 512. |
| model_name      | String         | The name of the Maritalk model to use. Options: "sabia-2-small", "sabia-2-medium". Default: "sabia-2-small". |
| api_key         | SecretString   | The Maritalk API Key to use for authentication.                  |
| temperature     | Float          | Controls randomness in the output. Range: [0.0, 1.0]. Default: 0.5. |
| endpoint_url    | String         | The Maritalk API endpoint. Default: https://api.maritalk.com.   |

#### Outputs

| Name  | Type          | Description                                                      |
|-------|---------------|------------------------------------------------------------------|
| model | LanguageModel | An instance of ChatMaritalk configured with the specified parameters. |

## Mistral

This component generates text using MistralAI LLMs.

For more information, see [Mistral AI documentation](https://docs.mistral.ai/).

### Parameters

#### Inputs
| Name                | Type         | Description                                                                                   |
|---------------------|--------------|-----------------------------------------------------------------------------------------------|
| max_tokens          | Integer      | The maximum number of tokens to generate. Set to 0 for unlimited tokens (advanced).         |
| model_name          | String       | The name of the Mistral AI model to use. Options include "open-mixtral-8x7b", "open-mixtral-8x22b", "mistral-small-latest", "mistral-medium-latest", "mistral-large-latest", and "codestral-latest". Default: "codestral-latest". |
| mistral_api_base    | String       | The base URL of the Mistral API. Defaults to https://api.mistral.ai/v1 (advanced).           |
| api_key             | SecretString | The Mistral API Key to use for authentication.                                                |
| temperature         | Float        | Controls randomness in the output. Default: 0.5.                                              |
| max_retries         | Integer      | Maximum number of retries for API calls. Default: 5 (advanced).                               |
| timeout             | Integer      | Timeout for API calls in seconds. Default: 60 (advanced).                                     |
| max_concurrent_requests | Integer  | Maximum number of concurrent API requests. Default: 3 (advanced).                             |
| top_p               | Float        | Nucleus sampling parameter. Default: 1 (advanced).                                            |
| random_seed         | Integer      | Seed for random number generation. Default: 1 (advanced).                                     |
| safe_mode           | Boolean      | Enables safe mode for content generation (advanced).                                          |

#### Outputs
| Name   | Type          | Description                                         |
|--------|---------------|-----------------------------------------------------|
| model  | LanguageModel | An instance of ChatMistralAI configured with the specified parameters. |

## NVIDIA

This component generates text using NVIDIA LLMs.

For more information, see [NVIDIA AI Foundation Models documentation](https://developer.nvidia.com/ai-foundation-models).

### Parameters

#### Inputs
| Name                | Type         | Description                                                                                   |
|---------------------|--------------|-----------------------------------------------------------------------------------------------|
| max_tokens          | Integer      | The maximum number of tokens to generate. Set to 0 for unlimited tokens (advanced).         |
| model_name          | String       | The name of the NVIDIA model to use. Default: "mistralai/mixtral-8x7b-instruct-v0.1".        |
| base_url            | String       | The base URL of the NVIDIA API. Default: "https://integrate.api.nvidia.com/v1".             |
| nvidia_api_key      | SecretString | The NVIDIA API Key for authentication.                                                        |
| temperature         | Float        | Controls randomness in the output. Default: 0.1.                                              |
| seed                | Integer      | The seed controls the reproducibility of the job (advanced). Default: 1.                      |

#### Outputs
| Name   | Type          | Description                                         |
|--------|---------------|-----------------------------------------------------|
| model  | LanguageModel | An instance of ChatNVIDIA configured with the specified parameters. |

## Ollama

This component generates text using Ollama's language models.

For more information, see [Ollama documentation](https://ollama.com/).

### Parameters

#### Inputs
| Name                | Display Name  | Info                                        |
|---------------------|---------------|---------------------------------------------|
| Base URL            | Base URL      | Endpoint of the Ollama API.                 |
| Model Name          | Model Name    | The model name to use.                     |
| Temperature         | Temperature   | Controls the creativity of model responses. |

## OpenAI

This component generates text using OpenAI's language models.

For more information, see [OpenAI documentation](https://beta.openai.com/docs/).

### Parameters

#### Inputs

| Name                | Type          | Description                                                      |
|---------------------|---------------|------------------------------------------------------------------|
| api_key             | SecretString   | Your OpenAI API Key.                                             |
| model               | String         | The name of the OpenAI model to use. Options include "gpt-3.5-turbo" and "gpt-4". |
| max_tokens          | Integer        | The maximum number of tokens to generate. Set to 0 for unlimited tokens. |
| temperature         | Float          | Controls randomness in the output. Range: [0.0, 1.0]. Default: 0.7. |
| top_p               | Float          | Controls the nucleus sampling. Range: [0.0, 1.0]. Default: 1.0. |
| frequency_penalty   | Float          | Controls the frequency penalty. Range: [0.0, 2.0]. Default: 0.0. |
| presence_penalty    | Float          | Controls the presence penalty. Range: [0.0, 2.0]. Default: 0.0. |

#### Outputs

| Name  | Type          | Description                                                      |
|-------|---------------|------------------------------------------------------------------|
| model | LanguageModel | An instance of OpenAI model configured with the specified parameters. |

## Qianfan

This component generates text using Qianfan's language models.

For more information, see [Qianfan documentation](https://github.com/baidubce/bce-qianfan-sdk).

## Perplexity

This component generates text using Perplexity's language models.

For more information, see [Perplexity documentation](https://perplexity.ai/).

### Parameters

#### Inputs
| Name                | Type         | Description                                                                                   |
|---------------------|--------------|-----------------------------------------------------------------------------------------------|
| model_name          | String       | The name of the Perplexity model to use. Options include various Llama 3.1 models.          |
| max_output_tokens   | Integer      | The maximum number of tokens to generate.                                                    |
| api_key             | SecretString | The Perplexity API Key for authentication.                                                    |
| temperature         | Float        | Controls randomness in the output. Default: 0.75.                                            |
| top_p               | Float        | The maximum cumulative probability of tokens to consider when sampling (advanced).           |
| n                   | Integer      | Number of chat completions to generate for each prompt (advanced).                            |
| top_k               | Integer      | Number of top tokens to consider for top-k sampling. Must be positive (advanced).            |

#### Outputs
| Name   | Type          | Description                                         |
|--------|---------------|-----------------------------------------------------|
| model  | LanguageModel | An instance of ChatPerplexity configured with the specified parameters. |

## SambaNova

This component generates text using SambaNova LLMs.

For more information, see [Sambanova Cloud documentation](https://cloud.sambanova.ai/).

### Parameters

#### Inputs

| Name                | Type          | Description                                                      |
|---------------------|---------------|------------------------------------------------------------------|
| sambanova_url            | String      | Base URL path for API requests. Default: "https://api.sambanova.ai/v1/chat/completions".                 |
| sambanova_api_key             | SecretString   | Your SambaNova API Key.                                             |
| model_name               | String         | The name of the Sambanova model to use. Options include various Llama models. |
| max_tokens          | Integer        | The maximum number of tokens to generate. Set to 0 for unlimited tokens. |
| temperature         | Float          | Controls randomness in the output. Range: [0.0, 1.0]. Default: 0.07. |
#### Outputs

| Name  | Type          | Description                                                      |
|-------|---------------|------------------------------------------------------------------|
| model | LanguageModel | An instance of SambaNova model configured with the specified parameters. |

## VertexAI

This component generates text using Vertex AI LLMs.

For more information, see [Google Vertex AI documentation](https://cloud.google.com/vertex-ai).

### Parameters

#### Inputs
| Name                | Type         | Description                                                                                   |
|---------------------|--------------|-----------------------------------------------------------------------------------------------|
| credentials         | File         | JSON credentials file. Leave empty to fallback to environment variables. File type: JSON.    |
| model_name          | String       | The name of the Vertex AI model to use. Default: "gemini-1.5-pro".                           |
| project             | String       | The project ID (advanced).                                                                     |
| location            | String       | The location for the Vertex AI API. Default: "us-central1" (advanced).                       |
| max_output_tokens   | Integer      | The maximum number of tokens to generate (advanced).                                         |
| max_retries         | Integer      | Maximum number of retries for API calls. Default: 1 (advanced).                              |
| temperature         | Float        | Controls randomness in the output. Default: 0.0.                                             |
| top_k               | Integer      | The number of highest probability vocabulary tokens to keep for top-k-filtering (advanced).   |
| top_p               | Float        | The cumulative probability of parameter highest probability vocabulary tokens to keep for nucleus sampling. Default: 0.95 (advanced). |
| verbose             | Boolean      | Whether to print verbose output. Default: False (advanced).                                   |

#### Outputs
| Name   | Type          | Description                                         |
|--------|---------------|-----------------------------------------------------|
| model  | LanguageModel | An instance of ChatVertexAI configured with the specified parameters. |

