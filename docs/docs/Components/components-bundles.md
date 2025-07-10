---
title: Bundles
slug: /components-bundle-components
---

import Icon from "@site/src/components/icon";

Bundled components are based on standard Langflow functionality, so you add them to your flows and configure them in much the same way as the standard components.
This documentation summarizes each bundled component and its parameters.
For details about provider-specific aspects of bundled components, this documentation provides links to relevant component provider documentation.

## Agent bundles

**Agents** use LLMs as a brain to analyze problems and select external tools.

For more information, see [Agents](/agents).

### CrewAI bundles

This bundle represents Agents of CrewAI allowing for the creation of specialized AI agents with defined roles goals and capabilities within a crew.

For more information, see the [CrewAI agents documentation](https://docs.crewai.com/core-concepts/Agents/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| role | Role | The role of the agent. |
| goal | Goal | The objective of the agent. |
| backstory | Backstory | The backstory of the agent. |
| tools | Tools | The tools at the agent's disposal. |
| llm | Language Model | The language model that runs the agent. |
| memory | Memory | This determines whether the agent should have memory or not. |
| verbose | Verbose | This enables verbose output. |
| allow_delegation | Allow Delegation | This determines whether the agent is allowed to delegate tasks to other agents. |
| allow_code_execution | Allow Code Execution | This determines whether the agent is allowed to execute code. |
| kwargs | kwargs | Additional keyword arguments for the agent. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| output | Agent | The constructed CrewAI Agent object. |

</details>

#### Hierarchical Crew

This component represents a group of agents managing how they should collaborate and the tasks they should perform in a hierarchical structure. This component allows for the creation of a crew with a manager overseeing the task execution.

For more information, see the [CrewAI hierarchical crew ocumentation](https://docs.crewai.com/how-to/Hierarchical/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| agents | Agents | The list of Agent objects representing the crew members. |
| tasks | Tasks | The list of HierarchicalTask objects representing the tasks to be executed. |
| manager_llm | Manager LLM | The language model for the manager agent. |
| manager_agent | Manager Agent | The specific agent to act as the manager. |
| verbose | Verbose | This enables verbose output for detailed logging. |
| memory | Memory | The memory configuration for the crew. |
| use_cache | Use Cache | This enables caching of results. |
| max_rpm | Max RPM | This sets the maximum requests per minute. |
| share_crew | Share Crew | This determines if the crew information is shared among agents. |
| function_calling_llm | Function Calling LLM | The language model for function calling. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| crew | Crew | The constructed Crew object with hierarchical task execution. |

</details>

#### Sequential crew

This component represents a group of agents with tasks that are executed sequentially. This component allows for the creation of a crew that performs tasks in a specific order.

For more information, see the [CrewAI sequential crew documentation](https://docs.crewai.com/how-to/Sequential/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| tasks | Tasks | The list of SequentialTask objects representing the tasks to be executed. |
| verbose | Verbose | This enables verbose output for detailed logging. |
| memory | Memory | The memory configuration for the crew. |
| use_cache | Use Cache | This enables caching of results. |
| max_rpm | Max RPM | This sets the maximum requests per minute. |
| share_crew | Share Crew | This determines if the crew information is shared among agents. |
| function_calling_llm | Function Calling LLM | The language model for function calling. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| crew | Crew | The constructed Crew object with sequential task execution. |

</details>

#### Sequential task agent

This component creates a CrewAI Task and its associated Agent allowing for the definition of sequential tasks with specific agent roles and capabilities.

For more information, see the [CrewAI sequential agents documentation](https://docs.crewai.com/how-to/Sequential/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| role | Role | The role of the agent. |
| goal | Goal | The objective of the agent. |
| backstory | Backstory | The backstory of the agent. |
| tools | Tools | The tools at the agent's disposal. |
| llm | Language Model | The language model that runs the agent. |
| memory | Memory | This determines whether the agent should have memory or not. |
| verbose | Verbose | This enables verbose output. |
| allow_delegation | Allow Delegation | This determines whether the agent is allowed to delegate tasks to other agents. |
| allow_code_execution | Allow Code Execution | This determines whether the agent is allowed to execute code. |
| agent_kwargs | Agent kwargs | The additional kwargs for the agent. |
| task_description | Task Description | The descriptive text detailing the task's purpose and execution. |
| expected_output | Expected Task Output | The clear definition of the expected task outcome. |
| async_execution | Async Execution | The boolean flag indicating asynchronous task execution. |
| previous_task | Previous Task | The previous task in the sequence for chaining. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| task_output | Sequential Task | The list of SequentialTask objects representing the created tasks. |

</details>

### CSV Agent

This component creates a CSV agent from a CSV file and LLM.

For more information, see the [Langchain CSV agent documentation](https://python.langchain.com/api_reference/experimental/agents/langchain_experimental.agents.agent_toolkits.csv.base.create_csv_agent.html).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| llm | LanguageModel | The language model to use for the agent. |
| path | File | The path to the CSV file. |
| agent_type | String | The type of agent to create. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| agent | AgentExecutor | The CSV agent instance. |

</details>

### OpenAI Tools Agent

This component creates an OpenAI Tools Agent.

For more information, see the [Langchain OpenAI agent documentation](https://api.python.langchain.com/en/latest/agents/langchain.agents.openai_functions_agent.base.create_openai_functions_agent.html).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| llm | LanguageModel | The language model to use. |
| tools | List of Tools | The tools to give the agent access to. |
| system_prompt | String | The system prompt to provide context to the agent. |
| input_value | String | The user's input to the agent. |
| memory | Memory | The memory for the agent to use for context persistence. |
| max_iterations | Integer | The maximum number of iterations to allow the agent to execute. |
| verbose | Boolean | This determines whether to print out the agent's intermediate steps. |
| handle_parsing_errors | Boolean | This determines whether to handle parsing errors in the agent. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| agent | AgentExecutor | The OpenAI Tools agent instance. |
| output | String | The output from executing the agent on the input. |

</details>

### OpenAPI Agent

This component creates an agent for interacting with OpenAPI services.

For more information, see the [Langchain OpenAPI toolkit documentation](https://python.langchain.com/docs/integrations/tools/openapi/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| llm | LanguageModel | The language model to use. |
| openapi_spec | String | The OpenAPI specification for the service. |
| base_url | String | The base URL for the API. |
| headers | Dict | The optional headers for API requests. |
| agent_executor_kwargs | Dict | The optional parameters for the agent executor. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| agent | AgentExecutor | The OpenAPI agent instance. |

</details>

### SQL Agent

This component creates an agent for interacting with SQL databases.

For more information, see the [Langchain SQL agent documentation](https://python.langchain.com/docs/tutorials/sql_qa/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| llm | LanguageModel | The language model to use. |
| database | Database | The SQL database connection. |
| top_k | Integer | The number of results to return from a SELECT query. |
| use_tools | Boolean | This determines whether to use tools for query execution. |
| return_intermediate_steps | Boolean | This determines whether to return the agent's intermediate steps. |
| max_iterations | Integer | The maximum number of iterations to run the agent. |
| max_execution_time | Integer | The maximum execution time in seconds. |
| early_stopping_method | String | The method to use for early stopping. |
| verbose | Boolean | This determines whether to print the agent's thoughts. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| agent | AgentExecutor | The SQL agent instance. |

</details>

### Tool Calling Agent

This component creates an agent for structured tool calling with various language models.

For more information, see the [Langchain tool calling documentation](https://python.langchain.com/docs/concepts/tool_calling/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| llm | LanguageModel | The language model to use. |
| tools | List[Tool] | The list of tools available to the agent. |
| system_message | String | The system message to use for the agent. |
| return_intermediate_steps | Boolean | This determines whether to return the agent's intermediate steps. |
| max_iterations | Integer | The maximum number of iterations to run the agent. |
| max_execution_time | Integer | The maximum execution time in seconds. |
| early_stopping_method | String | The method to use for early stopping. |
| verbose | Boolean | This determines whether to print the agent's thoughts. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| agent | AgentExecutor | The tool calling agent instance. |

</details>

### XML Agent

This component creates an XML Agent using LangChain.

The agent uses XML formatting for tool instructions to the Language Model.

For more information, see the [Langchain XML Agent documentation](https://python.langchain.com/api_reference/langchain/agents/langchain.agents.xml.base.XMLAgent.html).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| llm | LanguageModel | The language model to use for the agent. |
| user_prompt | String | The custom prompt template for the agent with XML formatting instructions. |
| tools | List[Tool] | The list of tools available to the agent. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| agent | AgentExecutor | The XML Agent instance. |

</details>

## Embedding models bundles

Embedding model components in Langflow generate text embeddings using the selected Large Language Model.

For more information, see [Embedding models](/components-embedding-models).

For more information on a specific embedding model bundle, see the provider's documentation.

### AI/ML

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

### Amazon Bedrock Embeddings

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

### Astra DB vectorize

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

### Azure OpenAI Embeddings

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

### Cloudflare Workers AI Embeddings

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

### Cohere Embeddings

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

### Embedding similarity

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

### Google generative AI embeddings

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

### Hugging Face Embeddings

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

### Hugging Face embeddings inference

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

#### Connect the Hugging Face component to a local embeddings model

To run an embeddings inference locally, see the [HuggingFace documentation](https://huggingface.co/docs/text-embeddings-inference/local_cpu).

To connect the local Hugging Face model to the **Hugging Face embeddings inference** component and use it in a flow, follow these steps:

1. Create a [Vector store RAG flow](/vector-store-rag).
There are two embeddings models in this flow that you can replace with **Hugging Face** embeddings inference components.
2. Replace both **OpenAI** embeddings model components with **Hugging Face** model components.
3. Connect both **Hugging Face** components to the **Embeddings** ports of the **Astra DB vector store** components.
4. In the **Hugging Face** components, set the **Inference Endpoint** field to the URL of your local inference model. **The **API Key** field is not required for local inference.**
5. Run the flow. The local inference models generate embeddings for the input text.

### IBM watsonx embeddings

This component generates text using [IBM watsonx.ai](https://www.ibm.com/watsonx) foundation models.

To use **IBM watsonx.ai** embeddings components, replace an embeddings component with the IBM watsonx.ai component in a flow.

An example document processing flow looks like the following:

![IBM watsonx embeddings model loading a chroma-db with split text](/img/component-watsonx-embeddings-chroma.png)

This flow loads a PDF file from local storage and splits the text into chunks.

The **IBM watsonx** embeddings component converts the text chunks into embeddings, which are then stored in a Chroma DB vector store.

The values for **API endpoint**, **Project ID**, **API key**, and **Model Name** are found in your IBM watsonx.ai deployment.
For more information, see the [Langchain documentation](https://python.langchain.com/docs/integrations/text_embedding/ibm_watsonx/).

#### Default models

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

### LM Studio Embeddings

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

### MistralAI

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

### NVIDIA

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

### Ollama embeddings

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

### OpenAI Embeddings

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

### Text embedder

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

### VertexAI Embeddings

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

## Language model bundles

Language model components in Langflow generate text using the selected Large Language Model.

For more information, see [Language models](/components-models).

For more information on a specific model bundle, see the provider's documentation.

### AIML

This component creates a ChatOpenAI model instance using the AIML API.

For more information, see [AIML documentation](https://docs.aimlapi.com/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| max_tokens | Integer | The maximum number of tokens to generate. Set to 0 for unlimited tokens. Range: 0-128000. |
| model_kwargs | Dictionary | Additional keyword arguments for the model. |
| model_name | String | The name of the AIML model to use. Options are predefined in `AIML_CHAT_MODELS`. |
| aiml_api_base | String | The base URL of the AIML API. Defaults to `https://api.aimlapi.com`. |
| api_key | SecretString | The AIML API Key to use for the model. |
| temperature | Float | Controls randomness in the output. Default: `0.1`. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| model | LanguageModel | An instance of ChatOpenAI configured with the specified parameters. |

</details>

### Amazon Bedrock

This component generates text using Amazon Bedrock LLMs.

For more information, see [Amazon Bedrock documentation](https://docs.aws.amazon.com/bedrock).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| model_id | String | The ID of the Amazon Bedrock model to use. Options include various models. |
| aws_access_key | SecretString | AWS Access Key for authentication. |
| aws_secret_key | SecretString | AWS Secret Key for authentication. |
| aws_session_token | SecretString | The session key for your AWS account.
| credentials_profile_name | String | Name of the AWS credentials profile to use. |
| region_name | String | AWS region name. Default: `us-east-1`. |
| model_kwargs | Dictionary | Additional keyword arguments for the model. |
| endpoint_url | String | Custom endpoint URL for the Bedrock service. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| model | LanguageModel | An instance of ChatBedrock configured with the specified parameters. |

</details>

### Anthropic

This component allows the generation of text using Anthropic Chat and Language models.

For more information, see the [Anthropic documentation](https://docs.anthropic.com/en/docs/welcome).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| max_tokens | Integer | The maximum number of tokens to generate. Set to 0 for unlimited tokens. Default: `4096`. |
| model | String | The name of the Anthropic model to use. Options include various Claude 3 models. |
| anthropic_api_key | SecretString | Your Anthropic API key for authentication. |
| temperature | Float | Controls randomness in the output. Default: `0.1`. |
| anthropic_api_url | String | Endpoint of the Anthropic API. Defaults to `https://api.anthropic.com` if not specified (advanced). |
| prefill | String | Prefill text to guide the model's response (advanced). |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| model | LanguageModel | An instance of ChatAnthropic configured with the specified parameters. |

</details>

### Azure OpenAI

This component generates text using Azure OpenAI LLM.

For more information, see the [Azure OpenAI documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| Model Name | String | Specifies the name of the Azure OpenAI model to be used for text generation. |
| Azure Endpoint | String | Your Azure endpoint, including the resource. |
| Deployment Name | String | Specifies the name of the deployment. |
| API Version | String | Specifies the version of the Azure OpenAI API to be used. |
| API Key | SecretString | Your Azure OpenAI API key. |
| Temperature | Float | Specifies the sampling temperature. Defaults to `0.7`. |
| Max Tokens | Integer | Specifies the maximum number of tokens to generate. Defaults to `1000`. |
| Input Value | String | Specifies the input text for text generation. |
| Stream | Boolean | Specifies whether to stream the response from the model. Defaults to `False`. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| model | LanguageModel | An instance of AzureOpenAI configured with the specified parameters. |

</details>

### Cohere

This component generates text using Cohere's language models.

For more information, see the [Cohere documentation](https://cohere.ai/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| Cohere API Key | SecretString | Your Cohere API key. |
| Max Tokens | Integer | Specifies the maximum number of tokens to generate. Defaults to `256`. |
| Temperature | Float | Specifies the sampling temperature. Defaults to `0.75`. |
| Input Value | String | Specifies the input text for text generation. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| model | LanguageModel | An instance of the Cohere model configured with the specified parameters. |

</details>

### DeepSeek

This component generates text using DeepSeek's language models.

For more information, see the [DeepSeek documentation](https://api-docs.deepseek.com/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| max_tokens | Integer | Maximum number of tokens to generate. Set to `0` for unlimited. Range: `0-128000`. |
| model_kwargs | Dictionary | Additional keyword arguments for the model. |
| json_mode | Boolean | If `True`, outputs JSON regardless of passing a schema. |
| model_name | String | The DeepSeek model to use. Default: `deepseek-chat`. |
| api_base | String | Base URL for API requests. Default: `https://api.deepseek.com`. |
| api_key | SecretString | Your DeepSeek API key for authentication. |
| temperature | Float | Controls randomness in responses. Range: `[0.0, 2.0]`. Default: `1.0`. |
| seed | Integer | Number initialized for random number generation. Use the same seed integer for more reproducible results, and use a different seed number for more random results. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| model | LanguageModel | An instance of ChatOpenAI configured with the specified parameters. |

</details>

### Google Generative AI

This component generates text using Google's Generative AI models.

For more information, see the [Google Generative AI documentation](https://cloud.google.com/vertex-ai/docs/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| Google API Key | SecretString | Your Google API key to use for the Google Generative AI. |
| Model | String | The name of the model to use, such as `"gemini-pro"`. |
| Max Output Tokens | Integer | The maximum number of tokens to generate. |
| Temperature | Float | Run inference with this temperature. |
| Top K | Integer | Consider the set of top K most probable tokens. |
| Top P | Float | The maximum cumulative probability of tokens to consider when sampling. |
| N | Integer | Number of chat completions to generate for each prompt. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| model | LanguageModel | An instance of ChatGoogleGenerativeAI configured with the specified parameters. |

</details>

### Groq

This component generates text using Groq's language models.

1. To use this component in a flow, connect it as a **Model** in a flow like the [Basic prompting flow](/basic-prompting), or select it as the **Model Provider** if you're using an **Agent** component.

![Groq component in a basic prompting flow](/img/component-groq.png)

2. In the **Groq API Key** field, paste your Groq API key.
The Groq model component automatically retrieves a list of the latest models.
To refresh your list of models, click <Icon name="RefreshCw" aria-label="Refresh"/>.
3. In the **Model** field, select the model you want to use for your LLM.
This example uses [llama-3.1-8b-instant](https://console.groq.com/docs/model/llama-3.1-8b-instant), which Groq recommends for real-time conversational interfaces.
4. In the **Prompt** component, enter:
```text
You are a helpful assistant who supports their claims with sources.
```
5. Click **Playground** and ask your Groq LLM a question.
The responses include a list of sources.

For more information, see the [Groq documentation](https://groq.com/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| groq_api_key | SecretString | API key for the Groq API. |
| groq_api_base | String | Base URL path for API requests. Default: `https://api.groq.com`. |
| max_tokens | Integer | The maximum number of tokens to generate. |
| temperature | Float | Controls randomness in the output. Range: `[0.0, 1.0]`. Default: `0.1`. |
| n | Integer | Number of chat completions to generate for each prompt. |
| model_name | String | The name of the Groq model to use. Options are dynamically fetched from the Groq API. |
| tool_mode_enabled | Bool | If enabled, the component only displays models that work with tools. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| model | LanguageModel | An instance of ChatGroq configured with the specified parameters. |

</details>

### Hugging Face API

This component sends requests to the Hugging Face API to generate text using the model specified in the **Model ID** field.

The Hugging Face API is a hosted inference API for models hosted on Hugging Face, and requires a [Hugging Face API token](https://huggingface.co/docs/hub/security-tokens) to authenticate.

In this example based on the [Basic prompting flow](/basic-prompting), the **Hugging Face API** model component replaces the **Open AI** model. By selecting different hosted models, you can see how different models return different results.

1. Create a [Basic prompting flow](/basic-prompting).

2. Replace the **OpenAI** model component with a **Hugging Face API** model component.

3. In the **Hugging Face API** component, add your Hugging Face API token to the **API Token** field.

4. Open the **Playground** and ask a question to the model, and see how it responds.

5. Try different models, and see how they perform differently.

For more information, see the [Hugging Face documentation](https://huggingface.co/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| model_id | String | The model ID from Hugging Face Hub. For example, "gpt2", "facebook/bart-large". |
| huggingfacehub_api_token | SecretString | Your Hugging Face API token for authentication. |
| temperature | Float | Controls randomness in the output. Range: [0.0, 1.0]. Default: 0.7. |
| max_new_tokens | Integer | Maximum number of tokens to generate. Default: 512. |
| top_p | Float | Nucleus sampling parameter. Range: [0.0, 1.0]. Default: 0.95. |
| top_k | Integer | Top-k sampling parameter. Default: 50. |
| model_kwargs | Dictionary | Additional keyword arguments to pass to the model. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| model | LanguageModel | An instance of HuggingFaceHub configured with the specified parameters. |

</details>

### IBM watsonx.ai

This component generates text using [IBM watsonx.ai](https://www.ibm.com/watsonx) foundation models.

To use **IBM watsonx.ai** model components, replace a model component with the IBM watsonx.ai component in a flow.

An example flow looks like the following:

![IBM watsonx model component in a basic prompting flow](/img/component-watsonx-model.png)

The values for **API endpoint**, **Project ID**, **API key**, and **Model Name** are found in your IBM watsonx.ai deployment.
For more information, see the [Langchain documentation](https://python.langchain.com/docs/integrations/chat/ibm_watsonx/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| url | String | The base URL of the watsonx API. |
| project_id | String | Your watsonx Project ID. |
| api_key | SecretString | Your IBM watsonx API Key. |
| model_name | String | The name of the watsonx model to use. Options are dynamically fetched from the API. |
| max_tokens | Integer | The maximum number of tokens to generate. Default: `1000`. |
| stop_sequence | String | The sequence where generation should stop. |
| temperature | Float | Controls randomness in the output. Default: `0.1`. |
| top_p | Float | Controls nucleus sampling, which limits the model to tokens whose probability is below the `top_p` value. Range: Default: `0.9`. |
| frequency_penalty | Float | Controls frequency penalty. A positive value decreases the probability of repeating tokens, and a negative value increases the probability. Range: Default: `0.5`. |
| presence_penalty | Float | Controls presence penalty. A positive value increases the likelihood of new topics being introduced. Default: `0.3`. |
| seed | Integer | A random seed for the model. Default: `8`. |
| logprobs | Boolean | Whether to return log probabilities of output tokens or not. Default: `True`. |
| top_logprobs | Integer | The number of most likely tokens to return at each position. Default: `3`. |
| logit_bias | String | A JSON string of token IDs to bias or suppress. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| model | LanguageModel | An instance of [ChatWatsonx](https://python.langchain.com/docs/integrations/chat/ibm_watsonx/) configured with the specified parameters. |

</details>

### LMStudio

This component generates text using LM Studio's local language models.

For more information, see [LM Studio documentation](https://lmstudio.ai/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| base_url | String | The URL where LM Studio is running. Default: `"http://localhost:1234"`. |
| max_tokens | Integer | Maximum number of tokens to generate in the response. Default: `512`. |
| temperature | Float | Controls randomness in the output. Range: `[0.0, 2.0]`. Default: `0.7`. |
| top_p | Float | Controls diversity via nucleus sampling. Range: `[0.0, 1.0]`. Default: `1.0`. |
| stop | List[String] | List of strings that stop generation when encountered. |
| stream | Boolean | Whether to stream the response. Default: `False`. |
| presence_penalty | Float | Penalizes repeated tokens. Range: `[-2.0, 2.0]`. Default: `0.0`. |
| frequency_penalty | Float | Penalizes frequent tokens. Range: `[-2.0, 2.0]`. Default: `0.0`. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| model | LanguageModel | An instance of LMStudio configured with the specified parameters. |

</details>

### Maritalk

This component generates text using Maritalk LLMs.

For more information, see [Maritalk documentation](https://www.maritalk.com/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| max_tokens | Integer | The maximum number of tokens to generate. Set to `0` for unlimited tokens. Default: `512`. |
| model_name | String | The name of the Maritalk model to use. Options: `sabia-2-small`, `sabia-2-medium`. Default: `sabia-2-small`. |
| api_key | SecretString | The Maritalk API Key to use for authentication. |
| temperature | Float | Controls randomness in the output. Range: `[0.0, 1.0]`. Default: `0.5`. |
| endpoint_url | String | The Maritalk API endpoint. Default: `https://api.maritalk.com`. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| model | LanguageModel | An instance of ChatMaritalk configured with the specified parameters. |

</details>

### Mistral

This component generates text using MistralAI LLMs.

For more information, see [Mistral AI documentation](https://docs.mistral.ai/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| max_tokens | Integer | The maximum number of tokens to generate. Set to 0 for unlimited tokens (advanced). |
| model_name | String | The name of the Mistral AI model to use. Options include `open-mixtral-8x7b`, `open-mixtral-8x22b`, `mistral-small-latest`, `mistral-medium-latest`, `mistral-large-latest`, and `codestral-latest`. Default: `codestral-latest`. |
| mistral_api_base | String | The base URL of the Mistral API. Defaults to `https://api.mistral.ai/v1` (advanced). |
| api_key | SecretString | The Mistral API Key to use for authentication. |
| temperature | Float | Controls randomness in the output. Default: 0.5. |
| max_retries | Integer | Maximum number of retries for API calls. Default: 5 (advanced). |
| timeout | Integer | Timeout for API calls in seconds. Default: 60 (advanced). |
| max_concurrent_requests | Integer | Maximum number of concurrent API requests. Default: 3 (advanced). |
| top_p | Float | Nucleus sampling parameter. Default: 1 (advanced). |
| random_seed | Integer | Seed for random number generation. Default: 1 (advanced). |
| safe_mode | Boolean | Enables safe mode for content generation (advanced). |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| model | LanguageModel | An instance of ChatMistralAI configured with the specified parameters. |

</details>

### Novita AI

This component generates text using Novita AI's language models.

For more information, see [Novita AI documentation](https://novita.ai/docs/model-api/reference/llm/llm.html?utm_source=github_langflow&utm_medium=github_readme&utm_campaign=link).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| api_key | SecretString | Your Novita AI API Key. |
| model | String | The id of the Novita AI model to use. |
| max_tokens | Integer | The maximum number of tokens to generate. Set to 0 for unlimited tokens. |
| temperature | Float | Controls randomness in the output. Range: [0.0, 1.0]. Default: 0.7. |
| top_p | Float | Controls the nucleus sampling. Range: [0.0, 1.0]. Default: 1.0. |
| frequency_penalty | Float | Controls the frequency penalty. Range: [0.0, 2.0]. Default: 0.0. |
| presence_penalty | Float | Controls the presence penalty. Range: [0.0, 2.0]. Default: 0.0. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| model | LanguageModel | An instance of Novita AI model configured with the specified parameters. |

</details>

### NVIDIA

This component generates text using NVIDIA LLMs.

For more information, see [NVIDIA AI documentation](https://developer.nvidia.com/generative-ai).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| max_tokens | Integer | The maximum number of tokens to generate. Set to `0` for unlimited tokens (advanced). |
| model_name | String | The name of the NVIDIA model to use. Default: `mistralai/mixtral-8x7b-instruct-v0.1`. |
| base_url | String | The base URL of the NVIDIA API. Default: `https://integrate.api.nvidia.com/v1`. |
| nvidia_api_key | SecretString | The NVIDIA API Key for authentication. |
| temperature | Float | Controls randomness in the output. Default: `0.1`. |
| seed | Integer | The seed controls the reproducibility of the job (advanced). Default: `1`. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| model | LanguageModel | An instance of ChatNVIDIA configured with the specified parameters. |

</details>

### Ollama

This component generates text using Ollama's language models.

To use this component in a flow, connect Langflow to your locally running Ollama server and select a model.

1. In the Ollama component, in the **Base URL** field, enter the address for your locally running Ollama server.
This value is set as the `OLLAMA_HOST` environment variable in Ollama.
The default base URL is `http://127.0.0.1:11434`.
2. To refresh the server's list of models, click <Icon name="RefreshCw" aria-label="Refresh"/>.
3. In the **Model Name** field, select a model. This example uses `llama3.2:latest`.
4. Connect the **Ollama** model component to a flow. For example, this flow connects a local Ollama server running a Llama 3.2 model as the custom model for an [Agent](/components-agents) component.

![Ollama model as Agent custom model](/img/component-ollama-model.png)

For more information, see the [Ollama documentation](https://ollama.com/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| Base URL | String | Endpoint of the Ollama API. |
| Model Name | String | The model name to use. |
| Temperature | Float | Controls the creativity of model responses. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| model | LanguageModel | An instance of an Ollama model configured with the specified parameters. |

</details>

### OpenAI

This component generates text using OpenAI's language models.

For more information, see [OpenAI documentation](https://beta.openai.com/docs/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| api_key | SecretString | Your OpenAI API Key. |
| model | String | The name of the OpenAI model to use. Options include "gpt-3.5-turbo" and "gpt-4". |
| max_tokens | Integer | The maximum number of tokens to generate. Set to 0 for unlimited tokens. |
| temperature | Float | Controls randomness in the output. Range: [0.0, 1.0]. Default: 0.7. |
| top_p | Float | Controls the nucleus sampling. Range: [0.0, 1.0]. Default: 1.0. |
| frequency_penalty | Float | Controls the frequency penalty. Range: [0.0, 2.0]. Default: 0.0. |
| presence_penalty | Float | Controls the presence penalty. Range: [0.0, 2.0]. Default: 0.0. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| model | LanguageModel | An instance of OpenAI model configured with the specified parameters. |

</details>

### OpenRouter

This component generates text using OpenRouter's unified API for multiple AI models from different providers.

For more information, see [OpenRouter documentation](https://openrouter.ai/docs).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| api_key | SecretString | Your OpenRouter API key for authentication. |
| site_url | String | Your site URL for OpenRouter rankings (advanced). |
| app_name | String | Your app name for OpenRouter rankings (advanced). |
| provider | String | The AI model provider to use. |
| model_name | String | The specific model to use for chat completion. |
| temperature | Float | Controls randomness in the output. Range: [0.0, 2.0]. Default: 0.7. |
| max_tokens | Integer | The maximum number of tokens to generate (advanced). |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| model | LanguageModel | An instance of ChatOpenAI configured with the specified parameters. |

</details>

### Perplexity

This component generates text using Perplexity's language models.

For more information, see [Perplexity documentation](https://perplexity.ai/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| model_name | String | The name of the Perplexity model to use. Options include various Llama 3.1 models. |
| max_output_tokens | Integer | The maximum number of tokens to generate. |
| api_key | SecretString | The Perplexity API Key for authentication. |
| temperature | Float | Controls randomness in the output. Default: 0.75. |
| top_p | Float | The maximum cumulative probability of tokens to consider when sampling (advanced). |
| n | Integer | Number of chat completions to generate for each prompt (advanced). |
| top_k | Integer | Number of top tokens to consider for top-k sampling. Must be positive (advanced). |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| model | LanguageModel | An instance of ChatPerplexity configured with the specified parameters. |

</details>

### Qianfan

This component generates text using Qianfan's language models.

For more information, see [Qianfan documentation](https://github.com/baidubce/bce-qianfan-sdk).

### SambaNova

This component generates text using SambaNova LLMs.

For more information, see [Sambanova Cloud documentation](https://cloud.sambanova.ai/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| sambanova_url | String | Base URL path for API requests. Default: `https://api.sambanova.ai/v1/chat/completions`. |
| sambanova_api_key | SecretString | Your SambaNova API Key. |
| model_name | String | The name of the Sambanova model to use. Options include various Llama models. |
| max_tokens | Integer | The maximum number of tokens to generate. Set to 0 for unlimited tokens. |
| temperature | Float | Controls randomness in the output. Range: [0.0, 1.0]. Default: 0.07. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| model | LanguageModel | An instance of SambaNova model configured with the specified parameters. |

</details>

### VertexAI

This component generates text using Vertex AI LLMs.

For more information, see [Google Vertex AI documentation](https://cloud.google.com/vertex-ai).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| credentials | File | JSON credentials file. Leave empty to fall back to environment variables. File type: JSON. |
| model_name | String | The name of the Vertex AI model to use. Default: "gemini-1.5-pro". |
| project | String | The project ID (advanced). |
| location | String | The location for the Vertex AI API. Default: "us-central1" (advanced). |
| max_output_tokens | Integer | The maximum number of tokens to generate (advanced). |
| max_retries | Integer | Maximum number of retries for API calls. Default: 1 (advanced). |
| temperature | Float | Controls randomness in the output. Default: 0.0. |
| top_k | Integer | The number of highest probability vocabulary tokens to keep for top-k-filtering (advanced). |
| top_p | Float | The cumulative probability of parameter highest probability vocabulary tokens to keep for nucleus sampling. Default: 0.95 (advanced). |
| verbose | Boolean | Whether to print verbose output. Default: False (advanced). |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| model | LanguageModel | An instance of ChatVertexAI configured with the specified parameters. |

</details>

### xAI

This component generates text using xAI models like [Grok](https://x.ai/grok).

For more information, see the [xAI documentation](https://x.ai/).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type | Description |
|------|------|-------------|
| max_tokens | Integer | Maximum number of tokens to generate. Set to `0` for unlimited. Range: `0-128000`. |
| model_kwargs | Dictionary | Additional keyword arguments for the model. |
| json_mode | Boolean | If `True`, outputs JSON regardless of passing a schema. |
| model_name | String | The xAI model to use. Default: `grok-2-latest`. |
| base_url | String | Base URL for API requests. Default: `https://api.x.ai/v1`. |
| api_key | SecretString | Your xAI API key for authentication. |
| temperature | Float | Controls randomness in the output. Range: `[0.0, 2.0]`. Default: `0.1`. |
| seed | Integer | Controls reproducibility of the job. |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| model | LanguageModel | An instance of ChatOpenAI configured with the specified parameters. |

</details>

## Memory bundles

### AstraDBChatMemory Component

This component creates an `AstraDBChatMessageHistory` instance, which stores and retrieves chat messages using Astra DB, a cloud-native database service.

<details>
<summary>Parameters</summary>

**Inputs**

| Name             | Type          | Description                                                           |
|------------------|---------------|-----------------------------------------------------------------------|
| collection_name  | String        | The name of the Astra DB collection for storing messages. Required. |
| token            | SecretString  | The authentication token for Astra DB access. Required. |
| api_endpoint     | SecretString  | The API endpoint URL for the Astra DB service. Required. |
| namespace        | String        | The optional namespace within Astra DB for the collection. |
| session_id       | MessageText   | The unique identifier for the chat session. Uses the current session ID if not provided. |

**Outputs**

| Name            | Type                    | Description                                               |
|-----------------|-------------------------|-----------------------------------------------------------|
| message_history | BaseChatMessageHistory  | An instance of AstraDBChatMessageHistory for the session. |

</details>

### CassandraChatMemory Component

This component creates a `CassandraChatMessageHistory` instance, enabling storage and retrieval of chat messages using Apache Cassandra or DataStax Astra DB.

<details>
<summary>Parameters</summary>

**Inputs**

| Name           | Type          | Description                                                                   |
|----------------|---------------|-------------------------------------------------------------------------------|
| database_ref   | MessageText   | The contact points for the Cassandra database or Astra DB database ID. Required. |
| username       | MessageText   | The username for Cassandra. Leave empty for Astra DB. |
| token          | SecretString  | The password for Cassandra or the token for Astra DB. Required. |
| keyspace       | MessageText   | The keyspace in Cassandra or namespace in Astra DB. Required. |
| table_name     | MessageText   | The name of the table or collection for storing messages. Required. |
| session_id     | MessageText   | The unique identifier for the chat session. Optional. |
| cluster_kwargs | Dictionary    | Additional keyword arguments for the Cassandra cluster configuration. Optional. |

**Outputs**

| Name            | Type                    | Description                                                  |
|-----------------|-------------------------|--------------------------------------------------------------|
| message_history | BaseChatMessageHistory  | An instance of CassandraChatMessageHistory for the session. |

</details>

### Mem0 Chat Memory

The Mem0 Chat Memory component retrieves and stores chat messages using Mem0 memory storage.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| mem0_config | Mem0 Configuration | The configuration dictionary for initializing the Mem0 memory instance. |
| ingest_message | Message to Ingest | The message content to be ingested into Mem0 memory. |
| existing_memory | Existing Memory Instance | An optional existing Mem0 memory instance. |
| user_id | User ID | The identifier for the user associated with the messages. |
| search_query | Search Query | The input text for searching related memories in Mem0. |
| mem0_api_key | Mem0 API Key | The API key for the Mem0 platform. Leave empty to use the local version. |
| metadata | Metadata | The additional metadata to associate with the ingested message. |
| openai_api_key | OpenAI API Key | The API key for OpenAI. Required when using OpenAI embeddings without a provided configuration. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| memory | Mem0 Memory | The resulting Mem0 Memory object after ingesting data. |
| search_results | Search Results | The search results from querying Mem0 memory. |

</details>

### Redis Chat Memory

This component retrieves and stores chat messages from Redis.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| host | hostname | The IP address or hostname. |
| port | port | The Redis Port Number. |
| database | database | The Redis database. |
| username | Username | The Redis username. |
| password | Password | The password for the username. |
| key_prefix | Key prefix | The key prefix. |
| session_id | Session ID | The unique session identifier for the message. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| memory | Memory | The Redis chat message history object. |

</details>

### ZepChatMemory Component

This component creates a `ZepChatMessageHistory` instance, enabling storage and retrieval of chat messages using Zep, a memory server for Large Language Models (LLMs).

<details>
<summary>Parameters</summary>

**Inputs**

| Name          | Type          | Description                                               |
|---------------|---------------|-----------------------------------------------------------|
| url           | MessageText   | The URL of the Zep instance. Required. |
| api_key       | SecretString  | The API Key for authentication with the Zep instance. |
| api_base_path | Dropdown      | The API version to use. Options include api/v1 or api/v2. |
| session_id    | MessageText   | The unique identifier for the chat session. Optional. |

**Outputs**

| Name            | Type                    | Description                                           |
|-----------------|-------------------------|-------------------------------------------------------|
| message_history | BaseChatMessageHistory  | An instance of ZepChatMessageHistory for the session. |

</details>