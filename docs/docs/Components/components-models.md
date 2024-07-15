---
title: Models
sidebar_position: 5
slug: /components-models
---



:::info

This page may contain outdated information. It will be updated as soon as possible.

:::




## Amazon Bedrock {#3b8ceacef3424234814f95895a25bf43}


This component facilitates the generation of text using the LLM (Large Language Model) model from Amazon Bedrock.


**Params**

- **Input Value:** Specifies the input text for text generation.
- **System Message (Optional):** A system message to pass to the model.
- **Model ID (Optional):** Specifies the model ID to be used for text generation. Defaults to `"anthropic.claude-instant-v1"`. Available options include:
	- `"ai21.j2-grande-instruct"`
	- `"ai21.j2-jumbo-instruct"`
	- `"ai21.j2-mid"`
	- `"ai21.j2-mid-v1"`
	- `"ai21.j2-ultra"`
	- `"ai21.j2-ultra-v1"`
	- `"anthropic.claude-instant-v1"`
	- `"anthropic.claude-v1"`
	- `"anthropic.claude-v2"`
	- `"cohere.command-text-v14"`
- **Credentials Profile Name (Optional):** Specifies the name of the credentials profile.
- **Region Name (Optional):** Specifies the region name.
- **Model Kwargs (Optional):** Additional keyword arguments for the model.
- **Endpoint URL (Optional):** Specifies the endpoint URL.
- **Streaming (Optional):** Specifies whether to stream the response from the model. Defaults to `False`.
- **Cache (Optional):** Specifies whether to cache the response.
- **Stream (Optional):** Specifies whether to stream the response from the model. Defaults to `False`.

NOTE


Ensure that necessary credentials are provided to connect to the Amazon Bedrock API. If connection fails, a ValueError will be raised.


---


## Anthropic {#a6ae46f98c4c4d389d44b8408bf151a1}


This component allows the generation of text using Anthropic Chat&Completion large language models.


**Params**

- **Model Name:** Specifies the name of the Anthropic model to be used for text generation. Available options include (and not limited to):
	- `"claude-2.1"`
	- `"claude-2.0"`
	- `"claude-instant-1.2"`
	- `"claude-instant-1"`
- **Anthropic API Key:** Your Anthropic API key.
- **Max Tokens (Optional):** Specifies the maximum number of tokens to generate. Defaults to `256`.
- **Temperature (Optional):** Specifies the sampling temperature. Defaults to `0.7`.
- **API Endpoint (Optional):** Specifies the endpoint of the Anthropic API. Defaults to `"https://api.anthropic.com"`if not specified.
- **Input Value:** Specifies the input text for text generation.
- **Stream (Optional):** Specifies whether to stream the response from the model. Defaults to `False`.
- **System Message (Optional):** A system message to pass to the model.

For detailed documentation and integration guides, please refer to the [Anthropic Component Documentation](https://python.langchain.com/docs/integrations/chat/anthropic).


---


## Azure OpenAI {#7e3bff29ce714479b07feeb4445680cd}


This component allows the generation of text using the LLM (Large Language Model) model from Azure OpenAI.


**Params**

- **Model Name:** Specifies the name of the Azure OpenAI model to be used for text generation. Available options include:
	- `"gpt-35-turbo"`
	- `"gpt-35-turbo-16k"`
	- `"gpt-35-turbo-instruct"`
	- `"gpt-4"`
	- `"gpt-4-32k"`
	- `"gpt-4-vision"`
	- `"gpt-4o"`
- **Azure Endpoint:** Your Azure endpoint, including the resource. Example: `https://example-resource.azure.openai.com/`.
- **Deployment Name:** Specifies the name of the deployment.
- **API Version:** Specifies the version of the Azure OpenAI API to be used. Available options include:
	- `"2023-03-15-preview"`
	- `"2023-05-15"`
	- `"2023-06-01-preview"`
	- `"2023-07-01-preview"`
	- `"2023-08-01-preview"`
	- `"2023-09-01-preview"`
	- `"2023-12-01-preview"`
- **API Key:** Your Azure OpenAI API key.
- **Temperature (Optional):** Specifies the sampling temperature. Defaults to `0.7`.
- **Max Tokens (Optional):** Specifies the maximum number of tokens to generate. Defaults to `1000`.
- **Input Value:** Specifies the input text for text generation.
- **Stream (Optional):** Specifies whether to stream the response from the model. Defaults to `False`.
- **System Message (Optional):** A system message to pass to the model.

For detailed documentation and integration guides, please refer to the [Azure OpenAI Component Documentation](https://python.langchain.com/docs/integrations/llms/azure_openai).


---


## Cohere {#706396a33bf94894966c95571252d78b}


This component enables text generation using Cohere large language models.


**Params**

- **Cohere API Key:** Your Cohere API key.
- **Max Tokens (Optional):** Specifies the maximum number of tokens to generate. Defaults to `256`.
- **Temperature (Optional):** Specifies the sampling temperature. Defaults to `0.75`.
- **Input Value:** Specifies the input text for text generation.
- **Stream (Optional):** Specifies whether to stream the response from the model. Defaults to `False`.
- **System Message (Optional):** A system message to pass to the model.

---


## Google Generative AI {#074d9623463449f99d41b44699800e8a}


This component enables text generation using Google Generative AI.


**Params**

- **Google API Key:** Your Google API key to use for the Google Generative AI.
- **Model:** The name of the model to use. Supported examples are `"gemini-pro"` and `"gemini-pro-vision"`.
- **Max Output Tokens (Optional):** The maximum number of tokens to generate.
- **Temperature:** Run inference with this temperature. Must be in the closed interval [0.0, 1.0].
- **Top K (Optional):** Decode using top-k sampling: consider the set of top_k most probable tokens. Must be positive.
- **Top P (Optional):** The maximum cumulative probability of tokens to consider when sampling.
- **N (Optional):** Number of chat completions to generate for each prompt. Note that the API may not return the full n completions if duplicates are generated.
- **Input Value:** The input to the model.
- **Stream (Optional):** Specifies whether to stream the response from the model. Defaults to `False`.
- **System Message (Optional):** A system message to pass to the model.

---


## Hugging Face API {#c1267b9a6b36487cb2ee127ce9b64dbb}


This component facilitates text generation using LLM models from the Hugging Face Inference API.


**Params**

- **Endpoint URL:** The URL of the Hugging Face Inference API endpoint. Should be provided along with necessary authentication credentials.
- **Task:** Specifies the task for text generation. Options include `"text2text-generation"`, `"text-generation"`, and `"summarization"`.
- **API Token:** The API token required for authentication with the Hugging Face Hub.
- **Model Keyword Arguments (Optional):** Additional keyword arguments for the model. Should be provided as a Python dictionary.
- **Input Value:** The input text for text generation.
- **Stream (Optional):** Specifies whether to stream the response from the model. Defaults to `False`.
- **System Message (Optional):** A system message to pass to the model.

---


## LiteLLM Model {#9fb59dad3b294a05966320d39f483a50}


Generates text using the `LiteLLM` collection of large language models.


**Parameters**

- **Model name:** The name of the model to use. For example, `gpt-3.5-turbo`. (Type: str)
- **API key:** The API key to use for accessing the provider's API. (Type: str, Optional)
- **Provider:** The provider of the API key. (Type: str, Choices: "OpenAI", "Azure", "Anthropic", "Replicate", "Cohere", "OpenRouter")
- **Temperature:** Controls the randomness of the text generation. (Type: float, Default: 0.7)
- **Model kwargs:** Additional keyword arguments for the model. (Type: Dict, Optional)
- **Top p:** Filter responses to keep the cumulative probability within the top p tokens. (Type: float, Optional)
- **Top k:** Filter responses to only include the top k tokens. (Type: int, Optional)
- **N:** Number of chat completions to generate for each prompt. (Type: int, Default: 1)
- **Max tokens:** The maximum number of tokens to generate for each chat completion. (Type: int, Default: 256)
- **Max retries:** Maximum number of retries for failed requests. (Type: int, Default: 6)
- **Verbose:** Whether to print verbose output. (Type: bool, Default: False)
- **Input:** The input prompt for text generation. (Type: str)
- **Stream:** Whether to stream the output. (Type: bool, Default: False)
- **System message:** System message to pass to the model. (Type: str, Optional)

---


## Ollama {#14e8e411d28d4711add53bfc3e52c6cd}


Generate text using Ollama Local LLMs.


**Parameters**

- **Base URL:** Endpoint of the Ollama API. Defaults to '[http://localhost:11434](http://localhost:11434/)' if not specified.
- **Model Name:** The model name to use. Refer to [Ollama Library](https://ollama.ai/library) for more models.
- **Temperature:** Controls the creativity of model responses. (Default: 0.8)
- **Cache:** Enable or disable caching. (Default: False)
- **Format:** Specify the format of the output (e.g., json). (Advanced)
- **Metadata:** Metadata to add to the run trace. (Advanced)
- **Mirostat:** Enable/disable Mirostat sampling for controlling perplexity. (Default: Disabled)
- **Mirostat Eta:** Learning rate for Mirostat algorithm. (Default: None) (Advanced)
- **Mirostat Tau:** Controls the balance between coherence and diversity of the output. (Default: None) (Advanced)
- **Context Window Size:** Size of the context window for generating tokens. (Default: None) (Advanced)
- **Number of GPUs:** Number of GPUs to use for computation. (Default: None) (Advanced)
- **Number of Threads:** Number of threads to use during computation. (Default: None) (Advanced)
- **Repeat Last N:** How far back the model looks to prevent repetition. (Default: None) (Advanced)
- **Repeat Penalty:** Penalty for repetitions in generated text. (Default: None) (Advanced)
- **TFS Z:** Tail free sampling value. (Default: None) (Advanced)
- **Timeout:** Timeout for the request stream. (Default: None) (Advanced)
- **Top K:** Limits token selection to top K. (Default: None) (Advanced)
- **Top P:** Works together with top-k. (Default: None) (Advanced)
- **Verbose:** Whether to print out response text.
- **Tags:** Tags to add to the run trace. (Advanced)
- **Stop Tokens:** List of tokens to signal the model to stop generating text. (Advanced)
- **System:** System to use for generating text. (Advanced)
- **Template:** Template to use for generating text. (Advanced)
- **Input:** The input text.
- **Stream:** Whether to stream the response.
- **System Message:** System message to pass to the model. (Advanced)

---


## OpenAI {#fe6cd793446748eda6eaad72e30f70b3}


This component facilitates text generation using OpenAI's models.


**Params**

- **Input Value:** The input text for text generation.
- **Max Tokens (Optional):** The maximum number of tokens to generate. Defaults to `256`.
- **Model Kwargs (Optional):** Additional keyword arguments for the model. Should be provided as a nested dictionary.
- **Model Name (Optional):** The name of the model to use. Defaults to `gpt-4-1106-preview`. Supported options include: `gpt-4-turbo-preview`, `gpt-4-0125-preview`, `gpt-4-1106-preview`, `gpt-4-vision-preview`, `gpt-3.5-turbo-0125`, `gpt-3.5-turbo-1106`.
- **OpenAI API Base (Optional):** The base URL of the OpenAI API. Defaults to `https://api.openai.com/v1`.
- **OpenAI API Key (Optional):** The API key for accessing the OpenAI API.
- **Temperature:** Controls the creativity of model responses. Defaults to `0.7`.
- **Stream (Optional):** Specifies whether to stream the response from the model. Defaults to `False`.
- **System Message (Optional):** System message to pass to the model.

---


## Qianfan {#6e4a6b2370ee4b9f8beb899e7cf9c8f6}


This component facilitates the generation of text using Baidu Qianfan chat models.


**Params**

- **Model Name:** Specifies the name of the Qianfan chat model to be used for text generation. Available options include:
	- `"ERNIE-Bot"`
	- `"ERNIE-Bot-turbo"`
	- `"BLOOMZ-7B"`
	- `"Llama-2-7b-chat"`
	- `"Llama-2-13b-chat"`
	- `"Llama-2-70b-chat"`
	- `"Qianfan-BLOOMZ-7B-compressed"`
	- `"Qianfan-Chinese-Llama-2-7B"`
	- `"ChatGLM2-6B-32K"`
	- `"AquilaChat-7B"`
- **Qianfan Ak:** Your Baidu Qianfan access key, obtainable from [here](https://cloud.baidu.com/product/wenxinworkshop).
- **Qianfan Sk:** Your Baidu Qianfan secret key, obtainable from [here](https://cloud.baidu.com/product/wenxinworkshop).
- **Top p (Optional):** Model parameter. Specifies the top-p value. Only supported in ERNIE-Bot and ERNIE-Bot-turbo models. Defaults to `0.8`.
- **Temperature (Optional):** Model parameter. Specifies the sampling temperature. Only supported in ERNIE-Bot and ERNIE-Bot-turbo models. Defaults to `0.95`.
- **Penalty Score (Optional):** Model parameter. Specifies the penalty score. Only supported in ERNIE-Bot and ERNIE-Bot-turbo models. Defaults to `1.0`.
- **Endpoint (Optional):** Endpoint of the Qianfan LLM, required if custom model is used.
- **Input Value:** Specifies the input text for text generation.
- **Stream (Optional):** Specifies whether to stream the response from the model. Defaults to `False`.
- **System Message (Optional):** A system message to pass to the model.

---


## Vertex AI {#86b7d539e17c436fb758c47ec3ffb084}


The `ChatVertexAI` is a component for generating text using Vertex AI Chat large language models API.


**Params**

- **Credentials:** The JSON file containing the credentials for accessing the Vertex AI Chat API.
- **Project:** The name of the project associated with the Vertex AI Chat API.
- **Examples (Optional):** List of examples to provide context for text generation.
- **Location:** The location of the Vertex AI Chat API service. Defaults to `us-central1`.
- **Max Output Tokens:** The maximum number of tokens to generate. Defaults to `128`.
- **Model Name:** The name of the model to use. Defaults to `chat-bison`.
- **Temperature:** Controls the creativity of model responses. Defaults to `0.0`.
- **Input Value:** The input text for text generation.
- **Top K:** Limits token selection to top K. Defaults to `40`.
- **Top P:** Works together with top-k. Defaults to `0.95`.
- **Verbose:** Whether to print out response text. Defaults to `False`.
- **Stream (Optional):** Specifies whether to stream the response from the model. Defaults to `False`.
- **System Message (Optional):** System message to pass to the model.
