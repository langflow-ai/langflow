from astra_assistants.tools.tool_interface import ToolInterface
from langflow.components.astra_assistants.tools.util import typed_dict_to_basemodel
from langflow.graph.graph.schema import GraphData

RawGraphDataModel = typed_dict_to_basemodel("GraphDataModel", GraphData)


class GraphDataModel(RawGraphDataModel):
    """
    ## Function Description
    Flowgen function will generate a langflow flow based on the graph data provided.
    Langflow is a low-code app builder for RAG and AI applications.
    Langflow has "components" which can be connected to create a flow.
    Each component has inputs and outputs.
    The flow is a graph where the nodes are components and the edges are connections between the components.

    There are many built-in components for langflow which you can use to chain into flows. In the following json each entry is a component:
    ```json
    [
    {
        "category": "prototypes/Pass",
        "component_name": "Pass",
        "inputs": [
            {
                "name": "ignored_message",
                "type": "str",
                "display_name": "Ignored Message",
                "info": "A second message to be ignored. Used as a workaround for continuity.",
                "required": false
            },
            {
                "name": "input_message",
                "type": "str",
                "display_name": "Input Message",
                "info": "The message to be passed forward.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "output_message",
                "types": [
                    "Message"
                ],
                "display_name": "Output Message",
                "method": "pass_message"
            }
        ],
        "description": "Forwards the input message, unchanged."
    },
    {
        "category": "prototypes/Listen",
        "component_name": "Listen",
        "inputs": [
            {
                "name": "name",
                "type": "str",
                "display_name": "Name",
                "info": "The name of the notification to listen for.",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "data",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": null
            }
        ],
        "description": "A component to listen for a notification."
    },
    {
        "category": "prototypes/Notify",
        "component_name": "Notify",
        "inputs": [
            {
                "name": "name",
                "type": "str",
                "display_name": "Name",
                "info": "The name of the notification.",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "data",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": null
            }
        ],
        "description": "A component to generate a notification to Get Notified component."
    },
    {
        "category": "prototypes/UpdateData",
        "component_name": "Update Data",
        "inputs": [
            {
                "name": "new_data",
                "type": "dict",
                "display_name": "New Data",
                "info": "The new data to update the record with.",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "data",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": null
            }
        ],
        "description": "Update Data with text-based key/value pairs, similar to updating a Python dictionary."
    },
    {
        "category": "prototypes/ConditionalRouter",
        "component_name": "Conditional Router",
        "inputs": [
            {
                "name": "input_text",
                "type": "str",
                "display_name": "Input Text",
                "info": "The primary text input for the operation.",
                "required": false
            },
            {
                "name": "match_text",
                "type": "str",
                "display_name": "Match Text",
                "info": "The text input to compare against.",
                "required": false
            },
            {
                "name": "message",
                "type": "str",
                "display_name": "Message",
                "info": "The message to pass through either route.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "true_result",
                "types": [
                    "Message"
                ],
                "display_name": "True Route",
                "method": "true_response"
            },
            {
                "name": "false_result",
                "types": [
                    "Message"
                ],
                "display_name": "False Route",
                "method": "false_response"
            }
        ],
        "description": "Routes an input message to a corresponding output based on text comparison."
    },
    {
        "category": "prototypes/RunnableExecutor",
        "component_name": "Runnable Executor",
        "inputs": [
            {
                "name": "runnable",
                "type": "other",
                "display_name": "Agent Executor",
                "info": "",
                "required": true
            },
            {
                "name": "input_key",
                "type": "str",
                "display_name": "Input Key",
                "info": "",
                "required": false
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": true
            },
            {
                "name": "output_key",
                "type": "str",
                "display_name": "Output Key",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "text",
                "types": [
                    "Message"
                ],
                "display_name": "Text",
                "method": "build_executor"
            }
        ],
        "description": "Execute a runnable. It will try to guess the input and output keys."
    },
    {
        "category": "prototypes/SubFlow",
        "component_name": "Sub Flow",
        "inputs": [],
        "outputs": [
            {
                "name": "flow_outputs",
                "types": [
                    "Data"
                ],
                "display_name": "Flow Outputs",
                "method": "generate_results"
            }
        ],
        "description": "Generates a Component from a Flow, with all of its inputs, and "
    },
    {
        "category": "prototypes/CreateData",
        "component_name": "Create Data",
        "inputs": [
            {
                "name": "text_key",
                "type": "str",
                "display_name": "Text Key",
                "info": "Key to be used as text.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "data",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "build_data"
            }
        ],
        "description": "Dynamically create a Data with a specified number of fields."
    },
    {
        "category": "prototypes/SQLExecutor",
        "component_name": "SQL Executor",
        "inputs": [
            {
                "name": "database_url",
                "type": "str",
                "display_name": "Database URL",
                "info": "The URL of the database.",
                "required": true
            },
            {
                "name": "query",
                "type": "str",
                "display_name": "query",
                "info": "",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "text",
                "types": [
                    "Text"
                ],
                "display_name": "Text",
                "method": null
            }
        ],
        "description": "Execute SQL query."
    },
    {
        "category": "prototypes/RunFlow",
        "component_name": "Run Flow",
        "inputs": [
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input Value",
                "info": "The input value to be processed by the flow.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "run_outputs",
                "types": [
                    "Data"
                ],
                "display_name": "Run Outputs",
                "method": "generate_results"
            }
        ],
        "description": "A component to run a flow."
    },
    {
        "category": "prototypes/PythonFunction",
        "component_name": "Python Function",
        "inputs": [],
        "outputs": [
            {
                "name": "function_output",
                "types": [
                    "Callable"
                ],
                "display_name": "Function Callable",
                "method": "get_function_callable"
            },
            {
                "name": "function_output_data",
                "types": [
                    "Data"
                ],
                "display_name": "Function Output (Data)",
                "method": "execute_function_data"
            },
            {
                "name": "function_output_str",
                "types": [
                    "Message"
                ],
                "display_name": "Function Output (Message)",
                "method": "execute_function_message"
            }
        ],
        "description": "Define and execute a Python function that returns a Data object or a Message."
    },
    {
        "category": "prototypes/FlowTool",
        "component_name": "Flow as Tool",
        "inputs": [],
        "outputs": [
            {
                "name": "api_build_tool",
                "types": [
                    "Tool"
                ],
                "display_name": "Tool",
                "method": "build_tool"
            }
        ],
        "description": "Construct a Tool from a function that runs the loaded Flow."
    },
    {
        "category": "prototypes/JSONCleaner",
        "component_name": "JSON Cleaner",
        "inputs": [
            {
                "name": "json_str",
                "type": "str",
                "display_name": "JSON String",
                "info": "The JSON string to be cleaned.",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "output",
                "types": [
                    "Message"
                ],
                "display_name": "Cleaned JSON String",
                "method": "clean_json"
            }
        ],
        "description": "Cleans the messy and sometimes incorrect JSON strings produced by LLMs so that they are fully compliant with the JSON spec."
    },
    {
        "category": "embeddings/Google Generative AI Embeddings",
        "component_name": "Google Generative AI Embeddings",
        "inputs": [
            {
                "name": "api_key",
                "type": "str",
                "display_name": "API Key",
                "info": "",
                "required": false
            },
            {
                "name": "model_name",
                "type": "str",
                "display_name": "Model Name",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "embeddings",
                "types": [
                    "Embeddings"
                ],
                "display_name": "Embeddings",
                "method": "build_embeddings"
            }
        ],
        "description": "Connect to Google's generative AI embeddings service using the GoogleGenerativeAIEmbeddings class, found in the langchain-google-genai package."
    },
    {
        "category": "embeddings/TextEmbedderComponent",
        "component_name": "Text Embedder",
        "inputs": [
            {
                "name": "embedding_model",
                "type": "other",
                "display_name": "Embedding Model",
                "info": "The embedding model to use for generating embeddings.",
                "required": false
            },
            {
                "name": "message",
                "type": "str",
                "display_name": "Message",
                "info": "The message to generate embeddings for.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "embeddings",
                "types": [
                    "Data"
                ],
                "display_name": "Embedding Data",
                "method": "generate_embeddings"
            }
        ],
        "description": "Generate embeddings for a given message using the specified embedding model."
    },
    {
        "category": "embeddings/OpenAIEmbeddings",
        "component_name": "OpenAI Embeddings",
        "inputs": [
            {
                "name": "client",
                "type": "str",
                "display_name": "Client",
                "info": "",
                "required": false
            },
            {
                "name": "deployment",
                "type": "str",
                "display_name": "Deployment",
                "info": "",
                "required": false
            },
            {
                "name": "openai_api_base",
                "type": "str",
                "display_name": "OpenAI API Base",
                "info": "",
                "required": false
            },
            {
                "name": "openai_api_key",
                "type": "str",
                "display_name": "OpenAI API Key",
                "info": "",
                "required": false
            },
            {
                "name": "openai_api_type",
                "type": "str",
                "display_name": "OpenAI API Type",
                "info": "",
                "required": false
            },
            {
                "name": "openai_api_version",
                "type": "str",
                "display_name": "OpenAI API Version",
                "info": "",
                "required": false
            },
            {
                "name": "openai_organization",
                "type": "str",
                "display_name": "OpenAI Organization",
                "info": "",
                "required": false
            },
            {
                "name": "openai_proxy",
                "type": "str",
                "display_name": "OpenAI Proxy",
                "info": "",
                "required": false
            },
            {
                "name": "tiktoken_model_name",
                "type": "str",
                "display_name": "TikToken Model Name",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "embeddings",
                "types": [
                    "Embeddings"
                ],
                "display_name": "Embeddings",
                "method": "build_embeddings"
            }
        ],
        "description": "Generate embeddings using OpenAI models."
    },
    {
        "category": "embeddings/VertexAIEmbeddings",
        "component_name": "VertexAI Embeddings",
        "inputs": [
            {
                "name": "location",
                "type": "str",
                "display_name": "Location",
                "info": "",
                "required": false
            },
            {
                "name": "model_name",
                "type": "str",
                "display_name": "Model Name",
                "info": "",
                "required": false
            },
            {
                "name": "project",
                "type": "str",
                "display_name": "Project",
                "info": "The project ID.",
                "required": false
            },
            {
                "name": "stop_sequences",
                "type": "str",
                "display_name": "Stop",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "embeddings",
                "types": [
                    "Embeddings"
                ],
                "display_name": "Embeddings",
                "method": "build_embeddings"
            }
        ],
        "description": "Generate embeddings using Google Cloud VertexAI models."
    },
    {
        "category": "embeddings/AzureOpenAIEmbeddings",
        "component_name": "Azure OpenAI Embeddings",
        "inputs": [
            {
                "name": "api_key",
                "type": "str",
                "display_name": "API Key",
                "info": "",
                "required": true
            },
            {
                "name": "azure_deployment",
                "type": "str",
                "display_name": "Deployment Name",
                "info": "",
                "required": true
            },
            {
                "name": "azure_endpoint",
                "type": "str",
                "display_name": "Azure Endpoint",
                "info": "Your Azure endpoint, including the resource. Example: `https://example-resource.azure.openai.com/`",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "embeddings",
                "types": [
                    "Embeddings"
                ],
                "display_name": "Embeddings",
                "method": "build_embeddings"
            }
        ],
        "description": "Generate embeddings using Azure OpenAI models."
    },
    {
        "category": "embeddings/AstraVectorize",
        "component_name": "Astra Vectorize",
        "inputs": [
            {
                "name": "api_key_name",
                "type": "str",
                "display_name": "API Key name",
                "info": "The name of the embeddings provider API key stored on Astra. If set, it will override the 'ProviderKey' in the authentication parameters.",
                "required": false
            },
            {
                "name": "model_name",
                "type": "str",
                "display_name": "Model Name",
                "info": "The embedding model to use for the selected provider. Each provider has a different set of models available (full list at https://docs.datastax.com/en/astra-db-serverless/databases/embedding-generation.html):\n\nAzure OpenAI: text-embedding-3-small, text-embedding-3-large, text-embedding-ada-002\n\nHugging Face - Dedicated: endpoint-defined-model\n\nHugging Face - Serverless: sentence-transformers/all-MiniLM-L6-v2, intfloat/multilingual-e5-large, intfloat/multilingual-e5-large-instruct, BAAI/bge-small-en-v1.5, BAAI/bge-base-en-v1.5, BAAI/bge-large-en-v1.5\n\nJina AI: jina-embeddings-v2-base-en, jina-embeddings-v2-base-de, jina-embeddings-v2-base-es, jina-embeddings-v2-base-code, jina-embeddings-v2-base-zh\n\nMistral AI: mistral-embed\n\nNVIDIA: NV-Embed-QA\n\nOpenAI: text-embedding-3-small, text-embedding-3-large, text-embedding-ada-002\n\nUpstage: solar-embedding-1-large\n\nVoyage AI: voyage-large-2-instruct, voyage-law-2, voyage-code-2, voyage-large-2, voyage-2",
                "required": true
            },
            {
                "name": "provider_api_key",
                "type": "str",
                "display_name": "Provider API Key",
                "info": "An alternative to the Astra Authentication that passes an API key for the provider with each request to Astra DB. This may be used when Vectorize is configured for the collection, but no corresponding provider secret is stored within Astra's key management system.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "config",
                "types": [
                    "dict"
                ],
                "display_name": "Vectorize",
                "method": "build_options"
            }
        ],
        "description": "Configuration options for Astra Vectorize server-side embeddings."
    },
    {
        "category": "embeddings/CohereEmbeddings",
        "component_name": "Cohere Embeddings",
        "inputs": [
            {
                "name": "cohere_api_key",
                "type": "str",
                "display_name": "Cohere API Key",
                "info": "",
                "required": false
            },
            {
                "name": "truncate",
                "type": "str",
                "display_name": "Truncate",
                "info": "",
                "required": false
            },
            {
                "name": "user_agent",
                "type": "str",
                "display_name": "User Agent",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "embeddings",
                "types": [
                    "Embeddings"
                ],
                "display_name": "Embeddings",
                "method": "build_embeddings"
            }
        ],
        "description": "Generate embeddings using Cohere models."
    },
    {
        "category": "embeddings/AmazonBedrockEmbeddings",
        "component_name": "Amazon Bedrock Embeddings",
        "inputs": [
            {
                "name": "aws_access_key",
                "type": "str",
                "display_name": "Access Key",
                "info": "",
                "required": false
            },
            {
                "name": "aws_secret_key",
                "type": "str",
                "display_name": "Secret Key",
                "info": "",
                "required": false
            },
            {
                "name": "credentials_profile_name",
                "type": "str",
                "display_name": "Credentials Profile Name",
                "info": "",
                "required": false
            },
            {
                "name": "endpoint_url",
                "type": "str",
                "display_name": " Endpoint URL",
                "info": "",
                "required": false
            },
            {
                "name": "region_name",
                "type": "str",
                "display_name": "Region Name",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "embeddings",
                "types": [
                    "Embeddings"
                ],
                "display_name": "Embeddings",
                "method": "build_embeddings"
            }
        ],
        "description": "Generate embeddings using Amazon Bedrock models."
    },
    {
        "category": "embeddings/AIMLEmbeddings",
        "component_name": "AI/ML Embeddings",
        "inputs": [
            {
                "name": "aiml_api_key",
                "type": "str",
                "display_name": "AI/ML API Key",
                "info": "",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "embeddings",
                "types": [
                    "Embeddings"
                ],
                "display_name": "Embeddings",
                "method": "build_embeddings"
            }
        ],
        "description": "Generate embeddings using the AI/ML API."
    },
    {
        "category": "embeddings/EmbeddingSimilarityComponent",
        "component_name": "Embedding Similarity",
        "inputs": [
            {
                "name": "embedding_vectors",
                "type": "other",
                "display_name": "Embedding Vectors",
                "info": "A list containing exactly two data objects with embedding vectors to compare.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "similarity_data",
                "types": [
                    "Data"
                ],
                "display_name": "Similarity Data",
                "method": "compute_similarity"
            }
        ],
        "description": "Compute selected form of similarity between two embedding vectors."
    },
    {
        "category": "embeddings/OllamaEmbeddings",
        "component_name": "Ollama Embeddings",
        "inputs": [
            {
                "name": "base_url",
                "type": "str",
                "display_name": "Ollama Base URL",
                "info": "",
                "required": false
            },
            {
                "name": "model",
                "type": "str",
                "display_name": "Ollama Model",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "embeddings",
                "types": [
                    "Embeddings"
                ],
                "display_name": "Embeddings",
                "method": "build_embeddings"
            }
        ],
        "description": "Generate embeddings using Ollama models."
    },
    {
        "category": "embeddings/HuggingFaceInferenceAPIEmbeddings",
        "component_name": "HuggingFace Embeddings Inference",
        "inputs": [
            {
                "name": "api_key",
                "type": "str",
                "display_name": "API Key",
                "info": "Required for non-local inference endpoints. Local inference does not require an API Key.",
                "required": false
            },
            {
                "name": "inference_endpoint",
                "type": "str",
                "display_name": "Inference Endpoint",
                "info": "Custom inference endpoint URL.",
                "required": true
            },
            {
                "name": "model_name",
                "type": "str",
                "display_name": "Model Name",
                "info": "The name of the model to use for text embeddings.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "embeddings",
                "types": [
                    "Embeddings"
                ],
                "display_name": "Embeddings",
                "method": "build_embeddings"
            }
        ],
        "description": "Generate embeddings using HuggingFace Text Embeddings Inference (TEI)"
    },
    {
        "category": "embeddings/NVIDIAEmbeddingsComponent",
        "component_name": "NVIDIA Embeddings",
        "inputs": [
            {
                "name": "base_url",
                "type": "str",
                "display_name": "NVIDIA Base URL",
                "info": "",
                "required": false
            },
            {
                "name": "nvidia_api_key",
                "type": "str",
                "display_name": "NVIDIA API Key",
                "info": "The NVIDIA API Key.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "embeddings",
                "types": [
                    "Embeddings"
                ],
                "display_name": "Embeddings",
                "method": "build_embeddings"
            }
        ],
        "description": "Generate embeddings using NVIDIA models."
    },
    {
        "category": "embeddings/MistalAIEmbeddings",
        "component_name": "MistralAI Embeddings",
        "inputs": [
            {
                "name": "endpoint",
                "type": "str",
                "display_name": "API Endpoint",
                "info": "",
                "required": false
            },
            {
                "name": "mistral_api_key",
                "type": "str",
                "display_name": "Mistral API Key",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "embeddings",
                "types": [
                    "Embeddings"
                ],
                "display_name": "Embeddings",
                "method": "build_embeddings"
            }
        ],
        "description": "Generate embeddings using MistralAI models."
    },
    {
        "category": "outputs/TextOutput",
        "component_name": "Text Output",
        "inputs": [
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Text",
                "info": "Text to be passed as output.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "text",
                "types": [
                    "Message"
                ],
                "display_name": "Text",
                "method": "text_response"
            }
        ],
        "description": "Display a text output in the Playground."
    },
    {
        "category": "outputs/ChatOutput",
        "component_name": "Chat Output",
        "inputs": [
            {
                "name": "data_template",
                "type": "str",
                "display_name": "Data Template",
                "info": "Template to convert Data to Text. If left empty, it will be dynamically set to the Data's text key.",
                "required": false
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Text",
                "info": "Message to be passed as output.",
                "required": false
            },
            {
                "name": "sender_name",
                "type": "str",
                "display_name": "Sender Name",
                "info": "Name of the sender.",
                "required": false
            },
            {
                "name": "session_id",
                "type": "str",
                "display_name": "Session ID",
                "info": "The session ID of the chat. If empty, the current session ID parameter will be used.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "message",
                "types": [
                    "Message"
                ],
                "display_name": "Message",
                "method": "message_response"
            }
        ],
        "description": "Display a chat message in the Playground."
    },
    {
        "category": "inputs/ChatInput",
        "component_name": "Chat Input",
        "inputs": [
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Text",
                "info": "Message to be passed as input.",
                "required": false
            },
            {
                "name": "sender_name",
                "type": "str",
                "display_name": "Sender Name",
                "info": "Name of the sender.",
                "required": false
            },
            {
                "name": "session_id",
                "type": "str",
                "display_name": "Session ID",
                "info": "The session ID of the chat. If empty, the current session ID parameter will be used.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "message",
                "types": [
                    "Message"
                ],
                "display_name": "Message",
                "method": "message_response"
            }
        ],
        "description": "Get chat inputs from the Playground."
    },
    {
        "category": "inputs/TextInput",
        "component_name": "Text Input",
        "inputs": [
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Text",
                "info": "Text to be passed as input.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "text",
                "types": [
                    "Message"
                ],
                "display_name": "Text",
                "method": "text_response"
            }
        ],
        "description": "Get text inputs from the Playground."
    },
    {
        "category": "memories/ZepChatMemory",
        "component_name": "Zep Chat Memory",
        "inputs": [
            {
                "name": "api_key",
                "type": "str",
                "display_name": "API Key",
                "info": "API Key for the Zep instance.",
                "required": false
            },
            {
                "name": "session_id",
                "type": "str",
                "display_name": "Session ID",
                "info": "Session ID for the message.",
                "required": false
            },
            {
                "name": "url",
                "type": "str",
                "display_name": "Zep URL",
                "info": "URL of the Zep instance.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "memory",
                "types": [
                    "BaseChatMessageHistory"
                ],
                "display_name": "Memory",
                "method": "build_message_history"
            }
        ],
        "description": "Retrieves and store chat messages from Zep."
    },
    {
        "category": "memories/AstraDBChatMemory",
        "component_name": "Astra DB Chat Memory",
        "inputs": [
            {
                "name": "api_endpoint",
                "type": "str",
                "display_name": "API Endpoint",
                "info": "API endpoint URL for the Astra DB service.",
                "required": true
            },
            {
                "name": "session_id",
                "type": "str",
                "display_name": "Session ID",
                "info": "The session ID of the chat. If empty, the current session ID parameter will be used.",
                "required": false
            },
            {
                "name": "token",
                "type": "str",
                "display_name": "Astra DB Application Token",
                "info": "Authentication token for accessing Astra DB.",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "memory",
                "types": [
                    "BaseChatMessageHistory"
                ],
                "display_name": "Memory",
                "method": "build_message_history"
            }
        ],
        "description": "Retrieves and store chat messages from Astra DB."
    },
    {
        "category": "memories/CassandraChatMemory",
        "component_name": "Cassandra Chat Memory",
        "inputs": [
            {
                "name": "database_ref",
                "type": "str",
                "display_name": "Contact Points / Astra Database ID",
                "info": "Contact points for the database (or AstraDB database ID)",
                "required": true
            },
            {
                "name": "keyspace",
                "type": "str",
                "display_name": "Keyspace",
                "info": "Table Keyspace (or AstraDB namespace).",
                "required": true
            },
            {
                "name": "session_id",
                "type": "str",
                "display_name": "Session ID",
                "info": "Session ID for the message.",
                "required": false
            },
            {
                "name": "table_name",
                "type": "str",
                "display_name": "Table Name",
                "info": "The name of the table (or AstraDB collection) where vectors will be stored.",
                "required": true
            },
            {
                "name": "token",
                "type": "str",
                "display_name": "Password / AstraDB Token",
                "info": "User password for the database (or AstraDB token).",
                "required": true
            },
            {
                "name": "username",
                "type": "str",
                "display_name": "Username",
                "info": "Username for the database (leave empty for AstraDB).",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "memory",
                "types": [
                    "BaseChatMessageHistory"
                ],
                "display_name": "Memory",
                "method": "build_message_history"
            }
        ],
        "description": "Retrieves and store chat messages from Apache Cassandra."
    },
    {
        "category": "data/GmailLoaderComponent",
        "component_name": "Gmail Loader",
        "inputs": [
            {
                "name": "json_string",
                "type": "str",
                "display_name": "JSON String of the Service Account Token",
                "info": "JSON string containing OAuth 2.0 access token information for service account access",
                "required": true
            },
            {
                "name": "label_ids",
                "type": "str",
                "display_name": "Label IDs",
                "info": "Comma-separated list of label IDs to filter emails.",
                "required": true
            },
            {
                "name": "max_results",
                "type": "str",
                "display_name": "Max Results",
                "info": "Maximum number of emails to load.",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "data",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "load_emails"
            }
        ],
        "description": "Loads emails from Gmail using provided credentials."
    },
    {
        "category": "data/APIRequest",
        "component_name": "API Request",
        "inputs": [
            {
                "name": "query_params",
                "type": "other",
                "display_name": "Query Parameters",
                "info": "The query parameters to append to the URL.",
                "required": false
            },
            {
                "name": "body",
                "type": "NestedDict",
                "display_name": "Body",
                "info": "The body to send with the request as a dictionary (for POST, PATCH, PUT). This is populated when using the CURL field.",
                "required": false
            },
            {
                "name": "curl",
                "type": "str",
                "display_name": "Curl",
                "info": "Paste a curl command to populate the fields. This will fill in the dictionary fields for headers and body.",
                "required": false
            },
            {
                "name": "headers",
                "type": "NestedDict",
                "display_name": "Headers",
                "info": "The headers to send with the request as a dictionary. This is populated when using the CURL field.",
                "required": false
            },
            {
                "name": "urls",
                "type": "str",
                "display_name": "URLs",
                "info": "Enter one or more URLs, separated by commas.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "data",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "make_requests"
            }
        ],
        "description": "This component allows you to make HTTP requests to one or more URLs. You can provide headers and body as either dictionaries or Data objects. Additionally, you can append query parameters to the URLs.\n\n**Note:** Check advanced options for more settings."
    },
    {
        "category": "data/Webhook",
        "component_name": "Webhook Input",
        "inputs": [
            {
                "name": "data",
                "type": "str",
                "display_name": "Data",
                "info": "Use this field to quickly test the webhook component by providing a JSON payload.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "output_data",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "build_data"
            }
        ],
        "description": "Defines a webhook input for the flow."
    },
    {
        "category": "data/URL",
        "component_name": "URL",
        "inputs": [
            {
                "name": "urls",
                "type": "str",
                "display_name": "URLs",
                "info": "Enter one or more URLs, by clicking the '+' button.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "data",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "fetch_content"
            },
            {
                "name": "text",
                "types": [
                    "Message"
                ],
                "display_name": "Text",
                "method": "fetch_content_text"
            }
        ],
        "description": "Fetch content from one or more URLs."
    },
    {
        "category": "data/GoogleDriveSearchComponent",
        "component_name": "Google Drive Search",
        "inputs": [
            {
                "name": "query_string",
                "type": "str",
                "display_name": "Query String",
                "info": "The query string used for searching. You can edit this manually.",
                "required": false
            },
            {
                "name": "search_term",
                "type": "str",
                "display_name": "Search Term",
                "info": "The value to search for in the specified query item.",
                "required": true
            },
            {
                "name": "token_string",
                "type": "str",
                "display_name": "Token String",
                "info": "JSON string containing OAuth 2.0 access token information for service account access",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "doc_urls",
                "types": [
                    "Text"
                ],
                "display_name": "Document URLs",
                "method": "search_doc_urls"
            },
            {
                "name": "doc_ids",
                "types": [
                    "Text"
                ],
                "display_name": "Document IDs",
                "method": "search_doc_ids"
            },
            {
                "name": "doc_titles",
                "types": [
                    "Text"
                ],
                "display_name": "Document Titles",
                "method": "search_doc_titles"
            },
            {
                "name": "Data",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "search_data"
            }
        ],
        "description": "Searches Google Drive files using provided credentials and query parameters."
    },
    {
        "category": "data/File",
        "component_name": "File",
        "inputs": [],
        "outputs": [
            {
                "name": "data",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "load_file"
            }
        ],
        "description": "A generic file loader."
    },
    {
        "category": "data/GoogleDriveComponent",
        "component_name": "Google Drive Loader",
        "inputs": [
            {
                "name": "document_id",
                "type": "str",
                "display_name": "Document ID",
                "info": "Single Google Drive document ID",
                "required": true
            },
            {
                "name": "json_string",
                "type": "str",
                "display_name": "JSON String of the Service Account Token",
                "info": "JSON string containing OAuth 2.0 access token information for service account access",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "docs",
                "types": [
                    "Data"
                ],
                "display_name": "Loaded Documents",
                "method": "load_documents"
            }
        ],
        "description": "Loads documents from Google Drive using provided credentials."
    },
    {
        "category": "data/Directory",
        "component_name": "Directory",
        "inputs": [
            {
                "name": "path",
                "type": "str",
                "display_name": "Path",
                "info": "Path to the directory to load files from.",
                "required": false
            },
            {
                "name": "types",
                "type": "str",
                "display_name": "Types",
                "info": "File types to load. Leave empty to load all types.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "data",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "load_directory"
            }
        ],
        "description": "Recursively load files from a directory."
    },
    {
        "category": "toolkits/VectorStoreInfo",
        "component_name": "VectorStoreInfo",
        "inputs": [
            {
                "name": "input_vectorstore",
                "type": "other",
                "display_name": "Vector Store",
                "info": "",
                "required": true
            },
            {
                "name": "vectorstore_description",
                "type": "str",
                "display_name": "Description",
                "info": "Description of the VectorStore",
                "required": true
            },
            {
                "name": "vectorstore_name",
                "type": "str",
                "display_name": "Name",
                "info": "Name of the VectorStore",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "info",
                "types": [
                    "VectorStoreInfo"
                ],
                "display_name": "Vector Store Info",
                "method": "build_info"
            }
        ],
        "description": "Information about a VectorStore"
    },
    {
        "category": "toolkits/ComposioAPI",
        "component_name": "Composio Tools",
        "inputs": [
            {
                "name": "api_key",
                "type": "str",
                "display_name": "Composio API Key",
                "info": "Refer to https://docs.composio.dev/introduction/foundations/howtos/get_api_key",
                "required": true
            },
            {
                "name": "entity_id",
                "type": "str",
                "display_name": "Entity ID",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "api_run_model",
                "types": [],
                "display_name": "Data",
                "method": "run_model"
            },
            {
                "name": "api_build_tool",
                "types": [
                    "Tool"
                ],
                "display_name": "Tool",
                "method": "build_tool"
            }
        ],
        "description": "Use Composio toolset to run actions with your agent"
    },
    {
        "category": "toolkits/Metaphor",
        "component_name": "Metaphor",
        "inputs": [
            {
                "name": "metaphor_api_key",
                "type": "str",
                "display_name": "Metaphor API Key",
                "info": "",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "tool",
                "types": [
                    "Tool"
                ],
                "display_name": "Tool",
                "method": null
            },
            {
                "name": "basetoolkit",
                "types": [
                    "BaseToolkit"
                ],
                "display_name": "BaseToolkit",
                "method": null
            }
        ],
        "description": "Metaphor Toolkit"
    },
    {
        "category": "helpers/ParseJSONData",
        "component_name": "Parse JSON",
        "inputs": [
            {
                "name": "input_value",
                "type": "other",
                "display_name": "Input",
                "info": "Data object to filter.",
                "required": true
            },
            {
                "name": "query",
                "type": "str",
                "display_name": "JQ Query",
                "info": "JQ Query to filter the data. The input is always a JSON list.",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "filtered_data",
                "types": [
                    "Data"
                ],
                "display_name": "Filtered Data",
                "method": "filter_data"
            }
        ],
        "description": "Convert and extract JSON fields."
    },
    {
        "category": "helpers/FilterData",
        "component_name": "Filter Data",
        "inputs": [
            {
                "name": "data",
                "type": "other",
                "display_name": "Data",
                "info": "Data object to filter.",
                "required": false
            },
            {
                "name": "filter_criteria",
                "type": "str",
                "display_name": "Filter Criteria",
                "info": "List of keys to filter by.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "filtered_data",
                "types": [
                    "Data"
                ],
                "display_name": "Filtered Data",
                "method": "filter_data"
            }
        ],
        "description": "Filters a Data object based on a list of keys."
    },
    {
        "category": "helpers/CombineText",
        "component_name": "Combine Text",
        "inputs": [
            {
                "name": "delimiter",
                "type": "str",
                "display_name": "Delimiter",
                "info": "A string used to separate the two text inputs. Defaults to a whitespace.",
                "required": false
            },
            {
                "name": "text1",
                "type": "str",
                "display_name": "First Text",
                "info": "The first text input to concatenate.",
                "required": false
            },
            {
                "name": "text2",
                "type": "str",
                "display_name": "Second Text",
                "info": "The second text input to concatenate.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "combined_text",
                "types": [
                    "Message"
                ],
                "display_name": "Combined Text",
                "method": "combine_texts"
            }
        ],
        "description": "Concatenate two text sources into a single text chunk using a specified delimiter."
    },
    {
        "category": "helpers/IDGenerator",
        "component_name": "ID Generator",
        "inputs": [
            {
                "name": "unique_id",
                "type": "str",
                "display_name": "Value",
                "info": "The generated unique ID.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "id",
                "types": [
                    "Message"
                ],
                "display_name": "ID",
                "method": "generate_id"
            }
        ],
        "description": "Generates a unique ID."
    },
    {
        "category": "helpers/SequentialTaskComponent",
        "component_name": "Sequential Task",
        "inputs": [
            {
                "name": "agent",
                "type": "other",
                "display_name": "Agent",
                "info": "CrewAI Agent that will perform the task",
                "required": true
            },
            {
                "name": "task",
                "type": "other",
                "display_name": "Task",
                "info": "CrewAI Task that will perform the task",
                "required": false
            },
            {
                "name": "tools",
                "type": "other",
                "display_name": "Tools",
                "info": "List of tools/resources limited for task execution. Uses the Agent tools by default.",
                "required": false
            },
            {
                "name": "expected_output",
                "type": "str",
                "display_name": "Expected Output",
                "info": "Clear definition of expected task outcome.",
                "required": false
            },
            {
                "name": "task_description",
                "type": "str",
                "display_name": "Description",
                "info": "Descriptive text detailing task's purpose and execution.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "task_output",
                "types": [
                    "SequentialTask"
                ],
                "display_name": "Task",
                "method": "build_task"
            }
        ],
        "description": "Each task must have a description, an expected output and an agent responsible for execution."
    },
    {
        "category": "helpers/CustomComponent",
        "component_name": "Custom Component",
        "inputs": [
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input Value",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "output",
                "types": [
                    "Data"
                ],
                "display_name": "Output",
                "method": "build_output"
            }
        ],
        "description": "Use as a template to create your own component."
    },
    {
        "category": "helpers/ParseData",
        "component_name": "Parse Data",
        "inputs": [
            {
                "name": "data",
                "type": "other",
                "display_name": "Data",
                "info": "The data to convert to text.",
                "required": false
            },
            {
                "name": "template",
                "type": "str",
                "display_name": "Template",
                "info": "The template to use for formatting the data. It can contain the keys {text}, {data} or any other key in the Data.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "text",
                "types": [
                    "Message"
                ],
                "display_name": "Text",
                "method": "parse_data"
            }
        ],
        "description": "Convert Data into plain text following a specified template."
    },
    {
        "category": "helpers/StoreMessage",
        "component_name": "Store Message",
        "inputs": [
            {
                "name": "memory",
                "type": "other",
                "display_name": "External Memory",
                "info": "The external memory to store the message. If empty, it will use the Langflow tables.",
                "required": false
            },
            {
                "name": "message",
                "type": "str",
                "display_name": "Message",
                "info": "The chat message to be stored.",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "stored_messages",
                "types": [
                    "Message"
                ],
                "display_name": "Stored Messages",
                "method": "store_message"
            }
        ],
        "description": "Stores a chat message or text into Langflow tables or an external memory."
    },
    {
        "category": "helpers/SplitText",
        "component_name": "Split Text",
        "inputs": [
            {
                "name": "data_inputs",
                "type": "other",
                "display_name": "Data Inputs",
                "info": "The data to split.",
                "required": false
            },
            {
                "name": "separator",
                "type": "str",
                "display_name": "Separator",
                "info": "The character to split on. Defaults to newline.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "chunks",
                "types": [
                    "Data"
                ],
                "display_name": "Chunks",
                "method": "split_text"
            }
        ],
        "description": "Split text into chunks based on specified criteria."
    },
    {
        "category": "helpers/MergeData",
        "component_name": "Merge Data",
        "inputs": [],
        "outputs": [
            {
                "name": "data",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": null
            }
        ],
        "description": "Combines multiple data sources into a single unified Data object."
    },
    {
        "category": "helpers/Memory",
        "component_name": "Chat Memory",
        "inputs": [
            {
                "name": "memory",
                "type": "other",
                "display_name": "External Memory",
                "info": "Retrieve messages from an external memory. If empty, it will use the Langflow tables.",
                "required": false
            },
            {
                "name": "sender_name",
                "type": "str",
                "display_name": "Sender Name",
                "info": "Filter by sender name.",
                "required": false
            },
            {
                "name": "session_id",
                "type": "str",
                "display_name": "Session ID",
                "info": "The session ID of the chat. If empty, the current session ID parameter will be used.",
                "required": false
            },
            {
                "name": "template",
                "type": "str",
                "display_name": "Template",
                "info": "The template to use for formatting the data. It can contain the keys {text}, {sender} or any other key in the message data.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "messages",
                "types": [
                    "Data"
                ],
                "display_name": "Messages (Data)",
                "method": "retrieve_messages"
            },
            {
                "name": "messages_text",
                "types": [
                    "Message"
                ],
                "display_name": "Messages (Text)",
                "method": "retrieve_messages_as_text"
            },
            {
                "name": "lc_memory",
                "types": [
                    "BaseChatMemory"
                ],
                "display_name": "Memory",
                "method": "build_lc_memory"
            }
        ],
        "description": "Retrieves stored chat messages from Langflow tables or an external memory."
    },
    {
        "category": "helpers/HierarchicalTaskComponent",
        "component_name": "Hierarchical Task",
        "inputs": [
            {
                "name": "tools",
                "type": "other",
                "display_name": "Tools",
                "info": "List of tools/resources limited for task execution. Uses the Agent tools by default.",
                "required": false
            },
            {
                "name": "expected_output",
                "type": "str",
                "display_name": "Expected Output",
                "info": "Clear definition of expected task outcome.",
                "required": false
            },
            {
                "name": "task_description",
                "type": "str",
                "display_name": "Description",
                "info": "Descriptive text detailing task's purpose and execution.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "task_output",
                "types": [
                    "HierarchicalTask"
                ],
                "display_name": "Task",
                "method": "build_task"
            }
        ],
        "description": "Each task must have a description, an expected output and an agent responsible for execution."
    },
    {
        "category": "helpers/CreateList",
        "component_name": "Create List",
        "inputs": [],
        "outputs": [
            {
                "name": "list",
                "types": [
                    "Data"
                ],
                "display_name": "Data List",
                "method": "create_list"
            }
        ],
        "description": "Creates a list of texts."
    },
    {
        "category": "vectorstores/Chroma",
        "component_name": "Chroma DB",
        "inputs": [
            {
                "name": "embedding",
                "type": "other",
                "display_name": "Embedding",
                "info": "",
                "required": false
            },
            {
                "name": "ingest_data",
                "type": "other",
                "display_name": "Ingest Data",
                "info": "",
                "required": false
            },
            {
                "name": "search_query",
                "type": "str",
                "display_name": "Search Query",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "base_retriever",
                "types": [
                    "Retriever"
                ],
                "display_name": "Retriever",
                "method": "build_base_retriever"
            },
            {
                "name": "search_results",
                "types": [
                    "Data"
                ],
                "display_name": "Search Results",
                "method": "search_documents"
            },
            {
                "name": "vector_store",
                "types": [
                    "VectorStore"
                ],
                "display_name": "Vector Store",
                "method": "cast_vector_store"
            }
        ],
        "description": "Chroma Vector Store with search capabilities"
    },
    {
        "category": "vectorstores/CassandraGraph",
        "component_name": "Cassandra Graph",
        "inputs": [
            {
                "name": "embedding",
                "type": "other",
                "display_name": "Embedding",
                "info": "",
                "required": false
            },
            {
                "name": "ingest_data",
                "type": "other",
                "display_name": "Ingest Data",
                "info": "",
                "required": false
            },
            {
                "name": "database_ref",
                "type": "str",
                "display_name": "Contact Points / Astra Database ID",
                "info": "Contact points for the database (or AstraDB database ID)",
                "required": true
            },
            {
                "name": "keyspace",
                "type": "str",
                "display_name": "Keyspace",
                "info": "Table Keyspace (or AstraDB namespace).",
                "required": true
            },
            {
                "name": "search_query",
                "type": "str",
                "display_name": "Search Query",
                "info": "",
                "required": false
            },
            {
                "name": "table_name",
                "type": "str",
                "display_name": "Table Name",
                "info": "The name of the table (or AstraDB collection) where vectors will be stored.",
                "required": true
            },
            {
                "name": "token",
                "type": "str",
                "display_name": "Password / AstraDB Token",
                "info": "User password for the database (or AstraDB token).",
                "required": true
            },
            {
                "name": "username",
                "type": "str",
                "display_name": "Username",
                "info": "Username for the database (leave empty for AstraDB).",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "base_retriever",
                "types": [
                    "Retriever"
                ],
                "display_name": "Retriever",
                "method": "build_base_retriever"
            },
            {
                "name": "search_results",
                "types": [
                    "Data"
                ],
                "display_name": "Search Results",
                "method": "search_documents"
            },
            {
                "name": "vector_store",
                "types": [
                    "VectorStore"
                ],
                "display_name": "Vector Store",
                "method": "cast_vector_store"
            }
        ],
        "description": "Cassandra Graph Vector Store"
    },
    {
        "category": "vectorstores/HCD",
        "component_name": "Hyper-Converged Database",
        "inputs": [
            {
                "name": "embedding",
                "type": "other",
                "display_name": "Embedding or Astra Vectorize",
                "info": "Allows either an embedding model or an Astra Vectorize configuration.",
                "required": false
            },
            {
                "name": "ingest_data",
                "type": "other",
                "display_name": "Ingest Data",
                "info": "",
                "required": false
            },
            {
                "name": "api_endpoint",
                "type": "str",
                "display_name": "HCD API Endpoint",
                "info": "API endpoint URL for the HCD service.",
                "required": true
            },
            {
                "name": "ca_certificate",
                "type": "str",
                "display_name": "CA Certificate",
                "info": "Optional CA certificate for TLS connections to HCD.",
                "required": false
            },
            {
                "name": "password",
                "type": "str",
                "display_name": "HCD Password",
                "info": "Authentication password for accessing HCD.",
                "required": true
            },
            {
                "name": "search_input",
                "type": "str",
                "display_name": "Search Input",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "base_retriever",
                "types": [
                    "Retriever"
                ],
                "display_name": "Retriever",
                "method": "build_base_retriever"
            },
            {
                "name": "search_results",
                "types": [
                    "Data"
                ],
                "display_name": "Search Results",
                "method": "search_documents"
            },
            {
                "name": "vector_store",
                "types": [
                    "VectorStore"
                ],
                "display_name": "Vector Store",
                "method": "cast_vector_store"
            }
        ],
        "description": "Implementation of Vector Store using Hyper-Converged Database (HCD) with search capabilities"
    },
    {
        "category": "vectorstores/Couchbase",
        "component_name": "Couchbase",
        "inputs": [
            {
                "name": "embedding",
                "type": "other",
                "display_name": "Embedding",
                "info": "",
                "required": false
            },
            {
                "name": "ingest_data",
                "type": "other",
                "display_name": "Ingest Data",
                "info": "",
                "required": false
            },
            {
                "name": "couchbase_connection_string",
                "type": "str",
                "display_name": "Couchbase Cluster connection string",
                "info": "",
                "required": true
            },
            {
                "name": "couchbase_password",
                "type": "str",
                "display_name": "Couchbase password",
                "info": "",
                "required": true
            },
            {
                "name": "search_query",
                "type": "str",
                "display_name": "Search Query",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "base_retriever",
                "types": [
                    "Retriever"
                ],
                "display_name": "Retriever",
                "method": "build_base_retriever"
            },
            {
                "name": "search_results",
                "types": [
                    "Data"
                ],
                "display_name": "Search Results",
                "method": "search_documents"
            },
            {
                "name": "vector_store",
                "types": [
                    "VectorStore"
                ],
                "display_name": "Vector Store",
                "method": "cast_vector_store"
            }
        ],
        "description": "Couchbase Vector Store with search capabilities"
    },
    {
        "category": "vectorstores/FAISS",
        "component_name": "FAISS",
        "inputs": [
            {
                "name": "embedding",
                "type": "other",
                "display_name": "Embedding",
                "info": "",
                "required": false
            },
            {
                "name": "ingest_data",
                "type": "other",
                "display_name": "Ingest Data",
                "info": "",
                "required": false
            },
            {
                "name": "search_query",
                "type": "str",
                "display_name": "Search Query",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "base_retriever",
                "types": [
                    "Retriever"
                ],
                "display_name": "Retriever",
                "method": "build_base_retriever"
            },
            {
                "name": "search_results",
                "types": [
                    "Data"
                ],
                "display_name": "Search Results",
                "method": "search_documents"
            },
            {
                "name": "vector_store",
                "types": [
                    "VectorStore"
                ],
                "display_name": "Vector Store",
                "method": "cast_vector_store"
            }
        ],
        "description": "FAISS Vector Store with search capabilities"
    },
    {
        "category": "vectorstores/Redis",
        "component_name": "Redis",
        "inputs": [
            {
                "name": "embedding",
                "type": "other",
                "display_name": "Embedding",
                "info": "",
                "required": false
            },
            {
                "name": "ingest_data",
                "type": "other",
                "display_name": "Ingest Data",
                "info": "",
                "required": false
            },
            {
                "name": "redis_server_url",
                "type": "str",
                "display_name": "Redis Server Connection String",
                "info": "",
                "required": true
            },
            {
                "name": "search_query",
                "type": "str",
                "display_name": "Search Query",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "base_retriever",
                "types": [
                    "Retriever"
                ],
                "display_name": "Retriever",
                "method": "build_base_retriever"
            },
            {
                "name": "search_results",
                "types": [
                    "Data"
                ],
                "display_name": "Search Results",
                "method": "search_documents"
            },
            {
                "name": "vector_store",
                "types": [
                    "VectorStore"
                ],
                "display_name": "Vector Store",
                "method": "cast_vector_store"
            }
        ],
        "description": "Implementation of Vector Store using Redis"
    },
    {
        "category": "vectorstores/pgvector",
        "component_name": "PGVector",
        "inputs": [
            {
                "name": "embedding",
                "type": "other",
                "display_name": "Embedding",
                "info": "",
                "required": false
            },
            {
                "name": "ingest_data",
                "type": "other",
                "display_name": "Ingestion Data",
                "info": "",
                "required": false
            },
            {
                "name": "pg_server_url",
                "type": "str",
                "display_name": "PostgreSQL Server Connection String",
                "info": "",
                "required": true
            },
            {
                "name": "search_query",
                "type": "str",
                "display_name": "Search Query",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "base_retriever",
                "types": [
                    "Retriever"
                ],
                "display_name": "Retriever",
                "method": "build_base_retriever"
            },
            {
                "name": "search_results",
                "types": [
                    "Data"
                ],
                "display_name": "Search Results",
                "method": "search_documents"
            },
            {
                "name": "vector_store",
                "types": [
                    "VectorStore"
                ],
                "display_name": "Vector Store",
                "method": "cast_vector_store"
            }
        ],
        "description": "PGVector Vector Store with search capabilities"
    },
    {
        "category": "vectorstores/AstraDB",
        "component_name": "Astra DB",
        "inputs": [
            {
                "name": "embedding",
                "type": "other",
                "display_name": "Embedding or Astra Vectorize",
                "info": "Allows either an embedding model or an Astra Vectorize configuration.",
                "required": false
            },
            {
                "name": "ingest_data",
                "type": "other",
                "display_name": "Ingest Data",
                "info": "",
                "required": false
            },
            {
                "name": "api_endpoint",
                "type": "str",
                "display_name": "API Endpoint",
                "info": "API endpoint URL for the Astra DB service.",
                "required": true
            },
            {
                "name": "search_input",
                "type": "str",
                "display_name": "Search Input",
                "info": "",
                "required": false
            },
            {
                "name": "token",
                "type": "str",
                "display_name": "Astra DB Application Token",
                "info": "Authentication token for accessing Astra DB.",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "base_retriever",
                "types": [
                    "Retriever"
                ],
                "display_name": "Retriever",
                "method": "build_base_retriever"
            },
            {
                "name": "search_results",
                "types": [
                    "Data"
                ],
                "display_name": "Search Results",
                "method": "search_documents"
            },
            {
                "name": "vector_store",
                "types": [
                    "VectorStore"
                ],
                "display_name": "Vector Store",
                "method": "cast_vector_store"
            }
        ],
        "description": "Implementation of Vector Store using Astra DB with search capabilities"
    },
    {
        "category": "vectorstores/Upstash",
        "component_name": "Upstash",
        "inputs": [
            {
                "name": "embedding",
                "type": "other",
                "display_name": "Embedding",
                "info": "To use Upstash's embeddings, don't provide an embedding.",
                "required": false
            },
            {
                "name": "ingest_data",
                "type": "other",
                "display_name": "Ingest Data",
                "info": "",
                "required": false
            },
            {
                "name": "index_token",
                "type": "str",
                "display_name": "Index Token",
                "info": "The token for the Upstash index.",
                "required": true
            },
            {
                "name": "metadata_filter",
                "type": "str",
                "display_name": "Metadata Filter",
                "info": "Filters documents by metadata. Look at the documentation for more information.",
                "required": false
            },
            {
                "name": "search_query",
                "type": "str",
                "display_name": "Search Query",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "base_retriever",
                "types": [
                    "Retriever"
                ],
                "display_name": "Retriever",
                "method": "build_base_retriever"
            },
            {
                "name": "search_results",
                "types": [
                    "Data"
                ],
                "display_name": "Search Results",
                "method": "search_documents"
            },
            {
                "name": "vector_store",
                "types": [
                    "VectorStore"
                ],
                "display_name": "Vector Store",
                "method": "cast_vector_store"
            }
        ],
        "description": "Upstash Vector Store with search capabilities"
    },
    {
        "category": "vectorstores/MongoDBAtlasVector",
        "component_name": "MongoDB Atlas",
        "inputs": [
            {
                "name": "embedding",
                "type": "other",
                "display_name": "Embedding",
                "info": "",
                "required": false
            },
            {
                "name": "ingest_data",
                "type": "other",
                "display_name": "Ingest Data",
                "info": "",
                "required": false
            },
            {
                "name": "mongodb_atlas_cluster_uri",
                "type": "str",
                "display_name": "MongoDB Atlas Cluster URI",
                "info": "",
                "required": true
            },
            {
                "name": "search_query",
                "type": "str",
                "display_name": "Search Query",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "base_retriever",
                "types": [
                    "Retriever"
                ],
                "display_name": "Retriever",
                "method": "build_base_retriever"
            },
            {
                "name": "search_results",
                "types": [
                    "Data"
                ],
                "display_name": "Search Results",
                "method": "search_documents"
            },
            {
                "name": "vector_store",
                "types": [
                    "VectorStore"
                ],
                "display_name": "Vector Store",
                "method": "cast_vector_store"
            }
        ],
        "description": "MongoDB Atlas Vector Store with search capabilities"
    },
    {
        "category": "vectorstores/Weaviate",
        "component_name": "Weaviate",
        "inputs": [
            {
                "name": "embedding",
                "type": "other",
                "display_name": "Embedding",
                "info": "",
                "required": false
            },
            {
                "name": "ingest_data",
                "type": "other",
                "display_name": "Ingest Data",
                "info": "",
                "required": false
            },
            {
                "name": "api_key",
                "type": "str",
                "display_name": "API Key",
                "info": "",
                "required": false
            },
            {
                "name": "search_query",
                "type": "str",
                "display_name": "Search Query",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "base_retriever",
                "types": [
                    "Retriever"
                ],
                "display_name": "Retriever",
                "method": "build_base_retriever"
            },
            {
                "name": "search_results",
                "types": [
                    "Data"
                ],
                "display_name": "Search Results",
                "method": "search_documents"
            },
            {
                "name": "vector_store",
                "types": [
                    "VectorStore"
                ],
                "display_name": "Vector Store",
                "method": "cast_vector_store"
            }
        ],
        "description": "Weaviate Vector Store with search capabilities"
    },
    {
        "category": "vectorstores/SupabaseVectorStore",
        "component_name": "Supabase",
        "inputs": [
            {
                "name": "embedding",
                "type": "other",
                "display_name": "Embedding",
                "info": "",
                "required": false
            },
            {
                "name": "ingest_data",
                "type": "other",
                "display_name": "Ingest Data",
                "info": "",
                "required": false
            },
            {
                "name": "search_query",
                "type": "str",
                "display_name": "Search Query",
                "info": "",
                "required": false
            },
            {
                "name": "supabase_service_key",
                "type": "str",
                "display_name": "Supabase Service Key",
                "info": "",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "base_retriever",
                "types": [
                    "Retriever"
                ],
                "display_name": "Retriever",
                "method": "build_base_retriever"
            },
            {
                "name": "search_results",
                "types": [
                    "Data"
                ],
                "display_name": "Search Results",
                "method": "search_documents"
            },
            {
                "name": "vector_store",
                "types": [
                    "VectorStore"
                ],
                "display_name": "Vector Store",
                "method": "cast_vector_store"
            }
        ],
        "description": "Supabase Vector Store with search capabilities"
    },
    {
        "category": "vectorstores/Clickhouse",
        "component_name": "Clickhouse",
        "inputs": [
            {
                "name": "embedding",
                "type": "other",
                "display_name": "Embedding",
                "info": "",
                "required": false
            },
            {
                "name": "ingest_data",
                "type": "other",
                "display_name": "Ingest Data",
                "info": "",
                "required": false
            },
            {
                "name": "password",
                "type": "str",
                "display_name": "The password for username.",
                "info": "",
                "required": true
            },
            {
                "name": "search_query",
                "type": "str",
                "display_name": "Search Query",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "base_retriever",
                "types": [
                    "Retriever"
                ],
                "display_name": "Retriever",
                "method": "build_base_retriever"
            },
            {
                "name": "search_results",
                "types": [
                    "Data"
                ],
                "display_name": "Search Results",
                "method": "search_documents"
            },
            {
                "name": "vector_store",
                "types": [
                    "VectorStore"
                ],
                "display_name": "Vector Store",
                "method": "cast_vector_store"
            }
        ],
        "description": "Clickhouse Vector Store with search capabilities"
    },
    {
        "category": "vectorstores/Cassandra",
        "component_name": "Cassandra",
        "inputs": [
            {
                "name": "embedding",
                "type": "other",
                "display_name": "Embedding",
                "info": "",
                "required": false
            },
            {
                "name": "ingest_data",
                "type": "other",
                "display_name": "Ingest Data",
                "info": "",
                "required": false
            },
            {
                "name": "body_search",
                "type": "str",
                "display_name": "Search Body",
                "info": "Document textual search terms to apply to the search query.",
                "required": false
            },
            {
                "name": "database_ref",
                "type": "str",
                "display_name": "Contact Points / Astra Database ID",
                "info": "Contact points for the database (or AstraDB database ID)",
                "required": true
            },
            {
                "name": "keyspace",
                "type": "str",
                "display_name": "Keyspace",
                "info": "Table Keyspace (or AstraDB namespace).",
                "required": true
            },
            {
                "name": "search_query",
                "type": "str",
                "display_name": "Search Query",
                "info": "",
                "required": false
            },
            {
                "name": "table_name",
                "type": "str",
                "display_name": "Table Name",
                "info": "The name of the table (or AstraDB collection) where vectors will be stored.",
                "required": true
            },
            {
                "name": "token",
                "type": "str",
                "display_name": "Password / AstraDB Token",
                "info": "User password for the database (or AstraDB token).",
                "required": true
            },
            {
                "name": "username",
                "type": "str",
                "display_name": "Username",
                "info": "Username for the database (leave empty for AstraDB).",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "base_retriever",
                "types": [
                    "Retriever"
                ],
                "display_name": "Retriever",
                "method": "build_base_retriever"
            },
            {
                "name": "search_results",
                "types": [
                    "Data"
                ],
                "display_name": "Search Results",
                "method": "search_documents"
            },
            {
                "name": "vector_store",
                "types": [
                    "VectorStore"
                ],
                "display_name": "Vector Store",
                "method": "cast_vector_store"
            }
        ],
        "description": "Cassandra Vector Store with search capabilities"
    },
    {
        "category": "vectorstores/Milvus",
        "component_name": "Milvus",
        "inputs": [
            {
                "name": "embedding",
                "type": "other",
                "display_name": "Embedding",
                "info": "",
                "required": false
            },
            {
                "name": "ingest_data",
                "type": "other",
                "display_name": "Ingest Data",
                "info": "",
                "required": false
            },
            {
                "name": "password",
                "type": "str",
                "display_name": "Connection Password",
                "info": "Ignore this field if no password is required to make connection.",
                "required": false
            },
            {
                "name": "search_query",
                "type": "str",
                "display_name": "Search Query",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "base_retriever",
                "types": [
                    "Retriever"
                ],
                "display_name": "Retriever",
                "method": "build_base_retriever"
            },
            {
                "name": "search_results",
                "types": [
                    "Data"
                ],
                "display_name": "Search Results",
                "method": "search_documents"
            },
            {
                "name": "vector_store",
                "types": [
                    "VectorStore"
                ],
                "display_name": "Vector Store",
                "method": "cast_vector_store"
            }
        ],
        "description": "Milvus vector store with search capabilities"
    },
    {
        "category": "vectorstores/Vectara",
        "component_name": "Vectara",
        "inputs": [
            {
                "name": "embedding",
                "type": "other",
                "display_name": "Embedding",
                "info": "",
                "required": false
            },
            {
                "name": "ingest_data",
                "type": "other",
                "display_name": "Ingest Data",
                "info": "",
                "required": false
            },
            {
                "name": "search_query",
                "type": "str",
                "display_name": "Search Query",
                "info": "",
                "required": false
            },
            {
                "name": "vectara_api_key",
                "type": "str",
                "display_name": "Vectara API Key",
                "info": "",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "base_retriever",
                "types": [
                    "Retriever"
                ],
                "display_name": "Retriever",
                "method": "build_base_retriever"
            },
            {
                "name": "search_results",
                "types": [
                    "Data"
                ],
                "display_name": "Search Results",
                "method": "search_documents"
            },
            {
                "name": "vector_store",
                "types": [
                    "VectorStore"
                ],
                "display_name": "Vector Store",
                "method": "cast_vector_store"
            }
        ],
        "description": "Vectara Vector Store with search capabilities"
    },
    {
        "category": "vectorstores/Pinecone",
        "component_name": "Pinecone",
        "inputs": [
            {
                "name": "embedding",
                "type": "other",
                "display_name": "Embedding",
                "info": "",
                "required": false
            },
            {
                "name": "ingest_data",
                "type": "other",
                "display_name": "Ingest Data",
                "info": "",
                "required": false
            },
            {
                "name": "pinecone_api_key",
                "type": "str",
                "display_name": "Pinecone API Key",
                "info": "",
                "required": true
            },
            {
                "name": "search_query",
                "type": "str",
                "display_name": "Search Query",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "base_retriever",
                "types": [
                    "Retriever"
                ],
                "display_name": "Retriever",
                "method": "build_base_retriever"
            },
            {
                "name": "search_results",
                "types": [
                    "Data"
                ],
                "display_name": "Search Results",
                "method": "search_documents"
            },
            {
                "name": "vector_store",
                "types": [
                    "VectorStore"
                ],
                "display_name": "Vector Store",
                "method": "cast_vector_store"
            }
        ],
        "description": "Pinecone Vector Store with search capabilities"
    },
    {
        "category": "vectorstores/QdrantVectorStoreComponent",
        "component_name": "Qdrant",
        "inputs": [
            {
                "name": "embedding",
                "type": "other",
                "display_name": "Embedding",
                "info": "",
                "required": false
            },
            {
                "name": "ingest_data",
                "type": "other",
                "display_name": "Ingest Data",
                "info": "",
                "required": false
            },
            {
                "name": "api_key",
                "type": "str",
                "display_name": "API Key",
                "info": "",
                "required": false
            },
            {
                "name": "search_query",
                "type": "str",
                "display_name": "Search Query",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "base_retriever",
                "types": [
                    "Retriever"
                ],
                "display_name": "Retriever",
                "method": "build_base_retriever"
            },
            {
                "name": "search_results",
                "types": [
                    "Data"
                ],
                "display_name": "Search Results",
                "method": "search_documents"
            },
            {
                "name": "vector_store",
                "types": [
                    "VectorStore"
                ],
                "display_name": "Vector Store",
                "method": "cast_vector_store"
            }
        ],
        "description": "Qdrant Vector Store with search capabilities"
    },
    {
        "category": "vectorstores/VectaraRAG",
        "component_name": "Vectara RAG",
        "inputs": [
            {
                "name": "filter",
                "type": "str",
                "display_name": "Metadata Filters",
                "info": "The filter string to narrow the search to according to metadata attributes.",
                "required": false
            },
            {
                "name": "search_query",
                "type": "str",
                "display_name": "Search Query",
                "info": "The query to receive an answer on.",
                "required": false
            },
            {
                "name": "vectara_api_key",
                "type": "str",
                "display_name": "Vectara API Key",
                "info": "",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "answer",
                "types": [
                    "Message"
                ],
                "display_name": "Answer",
                "method": "generate_response"
            }
        ],
        "description": "Vectara's full end to end RAG"
    },
    {
        "category": "link_extractors/HtmlLinkExtractor",
        "component_name": "HTML Link Extractor",
        "inputs": [
            {
                "name": "data_input",
                "type": "other",
                "display_name": "Input",
                "info": "The texts from which to extract links.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "data",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "transform_data"
            }
        ],
        "description": "Extract hyperlinks from HTML content."
    },
    {
        "category": "models/GroqModel",
        "component_name": "Groq",
        "inputs": [
            {
                "name": "groq_api_base",
                "type": "str",
                "display_name": "Groq API Base",
                "info": "Base URL path for API requests, leave blank if not using a proxy or service emulator.",
                "required": false
            },
            {
                "name": "groq_api_key",
                "type": "str",
                "display_name": "Groq API Key",
                "info": "API key for the Groq API.",
                "required": false
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            },
            {
                "name": "system_message",
                "type": "str",
                "display_name": "System Message",
                "info": "System message to pass to the model.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "text_output",
                "types": [
                    "Message"
                ],
                "display_name": "Text",
                "method": "text_response"
            },
            {
                "name": "model_output",
                "types": [
                    "LanguageModel"
                ],
                "display_name": "Language Model",
                "method": "build_model"
            }
        ],
        "description": "Generate text using Groq."
    },
    {
        "category": "models/MistralModel",
        "component_name": "MistralAI",
        "inputs": [
            {
                "name": "api_key",
                "type": "str",
                "display_name": "Mistral API Key",
                "info": "The Mistral API Key to use for the Mistral model.",
                "required": false
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            },
            {
                "name": "system_message",
                "type": "str",
                "display_name": "System Message",
                "info": "System message to pass to the model.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "text_output",
                "types": [
                    "Message"
                ],
                "display_name": "Text",
                "method": "text_response"
            },
            {
                "name": "model_output",
                "types": [
                    "LanguageModel"
                ],
                "display_name": "Language Model",
                "method": "build_model"
            }
        ],
        "description": "Generates text using MistralAI LLMs."
    },
    {
        "category": "models/CohereModel",
        "component_name": "Cohere",
        "inputs": [
            {
                "name": "cohere_api_key",
                "type": "str",
                "display_name": "Cohere API Key",
                "info": "The Cohere API Key to use for the Cohere model.",
                "required": false
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            },
            {
                "name": "system_message",
                "type": "str",
                "display_name": "System Message",
                "info": "System message to pass to the model.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "text_output",
                "types": [
                    "Message"
                ],
                "display_name": "Text",
                "method": "text_response"
            },
            {
                "name": "model_output",
                "types": [
                    "LanguageModel"
                ],
                "display_name": "Language Model",
                "method": "build_model"
            }
        ],
        "description": "Generate text using Cohere LLMs."
    },
    {
        "category": "models/AIMLModel",
        "component_name": "AIML",
        "inputs": [
            {
                "name": "api_key",
                "type": "str",
                "display_name": "AIML API Key",
                "info": "The AIML API Key to use for the OpenAI model.",
                "required": false
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            },
            {
                "name": "system_message",
                "type": "str",
                "display_name": "System Message",
                "info": "System message to pass to the model.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "text_output",
                "types": [
                    "Message"
                ],
                "display_name": "Text",
                "method": "text_response"
            },
            {
                "name": "model_output",
                "types": [
                    "LanguageModel"
                ],
                "display_name": "Language Model",
                "method": "build_model"
            }
        ],
        "description": "Generates text using AIML LLMs."
    },
    {
        "category": "models/GoogleGenerativeAIModel",
        "component_name": "Google Generative AI",
        "inputs": [
            {
                "name": "google_api_key",
                "type": "str",
                "display_name": "Google API Key",
                "info": "The Google API Key to use for the Google Generative AI.",
                "required": false
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            },
            {
                "name": "system_message",
                "type": "str",
                "display_name": "System Message",
                "info": "System message to pass to the model.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "text_output",
                "types": [
                    "Message"
                ],
                "display_name": "Text",
                "method": "text_response"
            },
            {
                "name": "model_output",
                "types": [
                    "LanguageModel"
                ],
                "display_name": "Language Model",
                "method": "build_model"
            }
        ],
        "description": "Generate text using Google Generative AI."
    },
    {
        "category": "models/PerplexityModel",
        "component_name": "Perplexity",
        "inputs": [
            {
                "name": "api_key",
                "type": "str",
                "display_name": "Perplexity API Key",
                "info": "The Perplexity API Key to use for the Perplexity model.",
                "required": false
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            },
            {
                "name": "system_message",
                "type": "str",
                "display_name": "System Message",
                "info": "System message to pass to the model.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "text_output",
                "types": [
                    "Message"
                ],
                "display_name": "Text",
                "method": "text_response"
            },
            {
                "name": "model_output",
                "types": [
                    "LanguageModel"
                ],
                "display_name": "Language Model",
                "method": "build_model"
            }
        ],
        "description": "Generate text using Perplexity LLMs."
    },
    {
        "category": "models/VertexAiModel",
        "component_name": "Vertex AI",
        "inputs": [
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            },
            {
                "name": "model_name",
                "type": "str",
                "display_name": "Model Name",
                "info": "",
                "required": false
            },
            {
                "name": "system_message",
                "type": "str",
                "display_name": "System Message",
                "info": "System message to pass to the model.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "text_output",
                "types": [
                    "Message"
                ],
                "display_name": "Text",
                "method": "text_response"
            },
            {
                "name": "model_output",
                "types": [
                    "LanguageModel"
                ],
                "display_name": "Language Model",
                "method": "build_model"
            }
        ],
        "description": "Generate text using Vertex AI LLMs."
    },
    {
        "category": "models/AmazonBedrockModel",
        "component_name": "Amazon Bedrock",
        "inputs": [
            {
                "name": "aws_access_key",
                "type": "str",
                "display_name": "Access Key",
                "info": "",
                "required": false
            },
            {
                "name": "aws_secret_key",
                "type": "str",
                "display_name": "Secret Key",
                "info": "",
                "required": false
            },
            {
                "name": "credentials_profile_name",
                "type": "str",
                "display_name": "Credentials Profile Name",
                "info": "",
                "required": false
            },
            {
                "name": "endpoint_url",
                "type": "str",
                "display_name": "Endpoint URL",
                "info": "",
                "required": false
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            },
            {
                "name": "region_name",
                "type": "str",
                "display_name": "Region Name",
                "info": "",
                "required": false
            },
            {
                "name": "system_message",
                "type": "str",
                "display_name": "System Message",
                "info": "System message to pass to the model.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "text_output",
                "types": [
                    "Message"
                ],
                "display_name": "Text",
                "method": "text_response"
            },
            {
                "name": "model_output",
                "types": [
                    "LanguageModel"
                ],
                "display_name": "Language Model",
                "method": "build_model"
            }
        ],
        "description": "Generate text using Amazon Bedrock LLMs."
    },
    {
        "category": "models/OpenAIModel",
        "component_name": "OpenAI",
        "inputs": [
            {
                "name": "api_key",
                "type": "str",
                "display_name": "OpenAI API Key",
                "info": "The OpenAI API Key to use for the OpenAI model.",
                "required": false
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            },
            {
                "name": "system_message",
                "type": "str",
                "display_name": "System Message",
                "info": "System message to pass to the model.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "text_output",
                "types": [
                    "Message"
                ],
                "display_name": "Text",
                "method": "text_response"
            },
            {
                "name": "model_output",
                "types": [
                    "LanguageModel"
                ],
                "display_name": "Language Model",
                "method": "build_model"
            }
        ],
        "description": "Generates text using OpenAI LLMs."
    },
    {
        "category": "models/AzureOpenAIModel",
        "component_name": "Azure OpenAI",
        "inputs": [
            {
                "name": "api_key",
                "type": "str",
                "display_name": "API Key",
                "info": "",
                "required": false
            },
            {
                "name": "azure_deployment",
                "type": "str",
                "display_name": "Deployment Name",
                "info": "",
                "required": true
            },
            {
                "name": "azure_endpoint",
                "type": "str",
                "display_name": "Azure Endpoint",
                "info": "Your Azure endpoint, including the resource. Example: `https://example-resource.azure.openai.com/`",
                "required": true
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            },
            {
                "name": "system_message",
                "type": "str",
                "display_name": "System Message",
                "info": "System message to pass to the model.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "text_output",
                "types": [
                    "Message"
                ],
                "display_name": "Text",
                "method": "text_response"
            },
            {
                "name": "model_output",
                "types": [
                    "LanguageModel"
                ],
                "display_name": "Language Model",
                "method": "build_model"
            }
        ],
        "description": "Generate text using Azure OpenAI LLMs."
    },
    {
        "category": "models/NVIDIAModelComponent",
        "component_name": "NVIDIA",
        "inputs": [
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            },
            {
                "name": "nvidia_api_key",
                "type": "str",
                "display_name": "NVIDIA API Key",
                "info": "The NVIDIA API Key.",
                "required": false
            },
            {
                "name": "system_message",
                "type": "str",
                "display_name": "System Message",
                "info": "System message to pass to the model.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "text_output",
                "types": [
                    "Message"
                ],
                "display_name": "Text",
                "method": "text_response"
            },
            {
                "name": "model_output",
                "types": [
                    "LanguageModel"
                ],
                "display_name": "Language Model",
                "method": "build_model"
            }
        ],
        "description": "Generates text using NVIDIA LLMs."
    },
    {
        "category": "models/OllamaModel",
        "component_name": "Ollama",
        "inputs": [
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            },
            {
                "name": "system_message",
                "type": "str",
                "display_name": "System Message",
                "info": "System message to pass to the model.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "text_output",
                "types": [
                    "Message"
                ],
                "display_name": "Text",
                "method": "text_response"
            },
            {
                "name": "model_output",
                "types": [
                    "LanguageModel"
                ],
                "display_name": "Language Model",
                "method": "build_model"
            }
        ],
        "description": "Generate text using Ollama Local LLMs."
    },
    {
        "category": "models/HuggingFaceModel",
        "component_name": "HuggingFace",
        "inputs": [
            {
                "name": "huggingfacehub_api_token",
                "type": "str",
                "display_name": "API Token",
                "info": "",
                "required": false
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            },
            {
                "name": "system_message",
                "type": "str",
                "display_name": "System Message",
                "info": "System message to pass to the model.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "text_output",
                "types": [
                    "Message"
                ],
                "display_name": "Text",
                "method": "text_response"
            },
            {
                "name": "model_output",
                "types": [
                    "LanguageModel"
                ],
                "display_name": "Language Model",
                "method": "build_model"
            }
        ],
        "description": "Generate text using Hugging Face Inference APIs."
    },
    {
        "category": "models/Maritalk",
        "component_name": "Maritalk",
        "inputs": [
            {
                "name": "api_key",
                "type": "str",
                "display_name": "Maritalk API Key",
                "info": "The Maritalk API Key to use for the OpenAI model.",
                "required": false
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            },
            {
                "name": "system_message",
                "type": "str",
                "display_name": "System Message",
                "info": "System message to pass to the model.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "text_output",
                "types": [
                    "Message"
                ],
                "display_name": "Text",
                "method": "text_response"
            },
            {
                "name": "model_output",
                "types": [
                    "LanguageModel"
                ],
                "display_name": "Language Model",
                "method": "build_model"
            }
        ],
        "description": "Generates text using Maritalk LLMs."
    },
    {
        "category": "models/AnthropicModel",
        "component_name": "Anthropic",
        "inputs": [
            {
                "name": "anthropic_api_key",
                "type": "str",
                "display_name": "Anthropic API Key",
                "info": "Your Anthropic API key.",
                "required": false
            },
            {
                "name": "anthropic_api_url",
                "type": "str",
                "display_name": "Anthropic API URL",
                "info": "Endpoint of the Anthropic API. Defaults to 'https://api.anthropic.com' if not specified.",
                "required": false
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            },
            {
                "name": "prefill",
                "type": "str",
                "display_name": "Prefill",
                "info": "Prefill text to guide the model's response.",
                "required": false
            },
            {
                "name": "system_message",
                "type": "str",
                "display_name": "System Message",
                "info": "System message to pass to the model.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "text_output",
                "types": [
                    "Message"
                ],
                "display_name": "Text",
                "method": "text_response"
            },
            {
                "name": "model_output",
                "types": [
                    "LanguageModel"
                ],
                "display_name": "Language Model",
                "method": "build_model"
            }
        ],
        "description": "Generate text using Anthropic Chat&Completion LLMs with prefill support."
    },
    {
        "category": "models/BaiduQianfanChatModel",
        "component_name": "Qianfan",
        "inputs": [
            {
                "name": "endpoint",
                "type": "str",
                "display_name": "Endpoint",
                "info": "Endpoint of the Qianfan LLM, required if custom model used.",
                "required": false
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            },
            {
                "name": "qianfan_ak",
                "type": "str",
                "display_name": "Qianfan Ak",
                "info": "which you could get from  https://cloud.baidu.com/product/wenxinworkshop",
                "required": false
            },
            {
                "name": "qianfan_sk",
                "type": "str",
                "display_name": "Qianfan Sk",
                "info": "which you could get from  https://cloud.baidu.com/product/wenxinworkshop",
                "required": false
            },
            {
                "name": "system_message",
                "type": "str",
                "display_name": "System Message",
                "info": "System message to pass to the model.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "text_output",
                "types": [
                    "Message"
                ],
                "display_name": "Text",
                "method": "text_response"
            },
            {
                "name": "model_output",
                "types": [
                    "LanguageModel"
                ],
                "display_name": "Language Model",
                "method": "build_model"
            }
        ],
        "description": "Generate text using Baidu Qianfan LLMs."
    },
    {
        "category": "textsplitters/LanguageRecursiveTextSplitter",
        "component_name": "Language Recursive Text Splitter",
        "inputs": [
            {
                "name": "data_input",
                "type": "other",
                "display_name": "Input",
                "info": "The texts to split.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "data",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "transform_data"
            }
        ],
        "description": "Split text into chunks of a specified length based on language."
    },
    {
        "category": "textsplitters/NaturalLanguageTextSplitter",
        "component_name": "Natural Language Text Splitter",
        "inputs": [
            {
                "name": "data_input",
                "type": "other",
                "display_name": "Input",
                "info": "The text data to be split.",
                "required": false
            },
            {
                "name": "language",
                "type": "str",
                "display_name": "Language",
                "info": "The language of the text. Default is \"English\". Supports multiple languages for better text boundary recognition.",
                "required": false
            },
            {
                "name": "separator",
                "type": "str",
                "display_name": "Separator",
                "info": "The character(s) to use as a delimiter when splitting text.\nDefaults to \"\\n\\n\" if left empty.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "data",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "transform_data"
            }
        ],
        "description": "Split text based on natural language boundaries, optimized for a specified language."
    },
    {
        "category": "textsplitters/RecursiveCharacterTextSplitter",
        "component_name": "Recursive Character Text Splitter",
        "inputs": [
            {
                "name": "data_input",
                "type": "other",
                "display_name": "Input",
                "info": "The texts to split.",
                "required": false
            },
            {
                "name": "separators",
                "type": "str",
                "display_name": "Separators",
                "info": "The characters to split on.\nIf left empty defaults to [\"\\n\\n\", \"\\n\", \" \", \"\"].",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "data",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "transform_data"
            }
        ],
        "description": "Split text trying to keep all related text together."
    },
    {
        "category": "textsplitters/CharacterTextSplitter",
        "component_name": "CharacterTextSplitter",
        "inputs": [
            {
                "name": "data_input",
                "type": "other",
                "display_name": "Input",
                "info": "The texts to split.",
                "required": false
            },
            {
                "name": "separator",
                "type": "str",
                "display_name": "Separator",
                "info": "The characters to split on.\nIf left empty defaults to \"\\n\\n\".",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "data",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "transform_data"
            }
        ],
        "description": "Split text by number of characters."
    },
    {
        "category": "tools/SerpAPI",
        "component_name": "Serp Search API",
        "inputs": [
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            },
            {
                "name": "serpapi_api_key",
                "type": "str",
                "display_name": "SerpAPI API Key",
                "info": "",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "api_run_model",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "run_model"
            },
            {
                "name": "api_build_tool",
                "types": [
                    "Tool"
                ],
                "display_name": "Tool",
                "method": "build_tool"
            }
        ],
        "description": "Call Serp Search API with result limiting"
    },
    {
        "category": "tools/GleanAPI",
        "component_name": "Glean Search API",
        "inputs": [
            {
                "name": "glean_access_token",
                "type": "str",
                "display_name": "Glean Access Token",
                "info": "",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "api_run_model",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "run_model"
            },
            {
                "name": "api_build_tool",
                "types": [
                    "Tool"
                ],
                "display_name": "Tool",
                "method": "build_tool"
            }
        ],
        "description": "Call Glean Search API"
    },
    {
        "category": "tools/SearXNGTool",
        "component_name": "SearXNG Search Tool",
        "inputs": [
            {
                "name": "url",
                "type": "str",
                "display_name": "URL",
                "info": "",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "result_tool",
                "types": [
                    "Tool"
                ],
                "display_name": "Tool",
                "method": "build_tool"
            }
        ],
        "description": "A component that searches for tools using SearXNG."
    },
    {
        "category": "tools/DuckDuckGoSearch",
        "component_name": "DuckDuckGo Search",
        "inputs": [
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Search Query",
                "info": "",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "api_run_model",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "run_model"
            },
            {
                "name": "api_build_tool",
                "types": [
                    "Tool"
                ],
                "display_name": "Tool",
                "method": "build_tool"
            }
        ],
        "description": "Perform web searches using the DuckDuckGo search engine with result limiting"
    },
    {
        "category": "tools/RetrieverTool",
        "component_name": "RetrieverTool",
        "inputs": [
            {
                "name": "retriever",
                "type": "BaseRetriever",
                "display_name": "Retriever",
                "info": "Retriever to interact with",
                "required": true
            },
            {
                "name": "description",
                "type": "str",
                "display_name": "Description",
                "info": "Description of the tool",
                "required": true
            },
            {
                "name": "name",
                "type": "str",
                "display_name": "Name",
                "info": "Name of the tool",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "tool",
                "types": [
                    "Tool"
                ],
                "display_name": "Tool",
                "method": null
            }
        ],
        "description": "Tool for interacting with retriever"
    },
    {
        "category": "tools/CalculatorTool",
        "component_name": "Calculator",
        "inputs": [
            {
                "name": "expression",
                "type": "str",
                "display_name": "Expression",
                "info": "The arithmetic expression to evaluate (e.g., '4*4*(33/22)+12-20').",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "api_run_model",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "run_model"
            },
            {
                "name": "api_build_tool",
                "types": [
                    "Tool"
                ],
                "display_name": "Tool",
                "method": "build_tool"
            }
        ],
        "description": "Perform basic arithmetic operations on a given expression."
    },
    {
        "category": "tools/PythonCodeStructuredTool",
        "component_name": "Python Code Structured Tool",
        "inputs": [
            {
                "name": "_classes",
                "type": "str",
                "display_name": "Classes",
                "info": "",
                "required": false
            },
            {
                "name": "_functions",
                "type": "str",
                "display_name": "Functions",
                "info": "",
                "required": false
            },
            {
                "name": "global_variables",
                "type": "dict",
                "display_name": "Global Variables",
                "info": "Enter the global variables or Create Data Component.",
                "required": false
            },
            {
                "name": "tool_code",
                "type": "str",
                "display_name": "Tool Code",
                "info": "Enter the dataclass code.",
                "required": true
            },
            {
                "name": "tool_description",
                "type": "str",
                "display_name": "Description",
                "info": "Enter the description of the tool.",
                "required": true
            },
            {
                "name": "tool_name",
                "type": "str",
                "display_name": "Tool Name",
                "info": "Enter the name of the tool.",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "result_tool",
                "types": [
                    "Tool"
                ],
                "display_name": "Tool",
                "method": "build_tool"
            }
        ],
        "description": "structuredtool dataclass code to tool"
    },
    {
        "category": "tools/WikipediaAPI",
        "component_name": "Wikipedia API",
        "inputs": [
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            },
            {
                "name": "lang",
                "type": "str",
                "display_name": "Language",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "api_run_model",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "run_model"
            },
            {
                "name": "api_build_tool",
                "types": [
                    "Tool"
                ],
                "display_name": "Tool",
                "method": "build_tool"
            }
        ],
        "description": "Call Wikipedia API."
    },
    {
        "category": "tools/WolframAlphaAPI",
        "component_name": "WolframAlphaAPI",
        "inputs": [
            {
                "name": "app_id",
                "type": "str",
                "display_name": "App ID",
                "info": "",
                "required": true
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "api_run_model",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "run_model"
            },
            {
                "name": "api_build_tool",
                "types": [
                    "Tool"
                ],
                "display_name": "Tool",
                "method": "build_tool"
            }
        ],
        "description": "Call Wolfram Alpha API."
    },
    {
        "category": "tools/PythonREPLTool",
        "component_name": "Python REPL Tool",
        "inputs": [],
        "outputs": [
            {
                "name": "api_run_model",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "run_model"
            },
            {
                "name": "api_build_tool",
                "types": [
                    "Tool"
                ],
                "display_name": "Tool",
                "method": "build_tool"
            }
        ],
        "description": "A tool for running Python code in a REPL environment."
    },
    {
        "category": "tools/GoogleSearchAPI",
        "component_name": "Google Search API",
        "inputs": [
            {
                "name": "google_api_key",
                "type": "str",
                "display_name": "Google API Key",
                "info": "",
                "required": true
            },
            {
                "name": "google_cse_id",
                "type": "str",
                "display_name": "Google CSE ID",
                "info": "",
                "required": true
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "api_run_model",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "run_model"
            },
            {
                "name": "api_build_tool",
                "types": [
                    "Tool"
                ],
                "display_name": "Tool",
                "method": "build_tool"
            }
        ],
        "description": "Call Google Search API."
    },
    {
        "category": "tools/SearchAPI",
        "component_name": "Search API",
        "inputs": [
            {
                "name": "api_key",
                "type": "str",
                "display_name": "SearchAPI API Key",
                "info": "",
                "required": true
            },
            {
                "name": "engine",
                "type": "str",
                "display_name": "Engine",
                "info": "",
                "required": false
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "api_run_model",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "run_model"
            },
            {
                "name": "api_build_tool",
                "types": [
                    "Tool"
                ],
                "display_name": "Tool",
                "method": "build_tool"
            }
        ],
        "description": "Call the searchapi.io API with result limiting"
    },
    {
        "category": "tools/YFinanceTool",
        "component_name": "Yahoo Finance News Tool",
        "inputs": [
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Query",
                "info": "Input should be a company ticker. For example, AAPL for Apple, MSFT for Microsoft.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "api_run_model",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "run_model"
            },
            {
                "name": "tool",
                "types": [
                    "Tool"
                ],
                "display_name": "Tool",
                "method": "build_tool"
            }
        ],
        "description": "Tool for interacting with Yahoo Finance News."
    },
    {
        "category": "tools/GoogleSerperAPI",
        "component_name": "Google Serper API",
        "inputs": [
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            },
            {
                "name": "serper_api_key",
                "type": "str",
                "display_name": "Serper API Key",
                "info": "",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "api_run_model",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "run_model"
            },
            {
                "name": "api_build_tool",
                "types": [
                    "Tool"
                ],
                "display_name": "Tool",
                "method": "build_tool"
            }
        ],
        "description": "Call the Serper.dev Google Search API."
    },
    {
        "category": "tools/BingSearchAPI",
        "component_name": "Bing Search API",
        "inputs": [
            {
                "name": "bing_search_url",
                "type": "str",
                "display_name": "Bing Search URL",
                "info": "",
                "required": false
            },
            {
                "name": "bing_subscription_key",
                "type": "str",
                "display_name": "Bing Subscription Key",
                "info": "",
                "required": false
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "api_run_model",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "run_model"
            },
            {
                "name": "api_build_tool",
                "types": [
                    "Tool"
                ],
                "display_name": "Tool",
                "method": "build_tool"
            }
        ],
        "description": "Call the Bing Search API."
    },
    {
        "category": "astra_assistants/Dotenv",
        "component_name": "Dotenv",
        "inputs": [
            {
                "name": "dotenv_file_content",
                "type": "str",
                "display_name": "Dotenv file content",
                "info": "Paste the content of your .env file directly, since contents are sensitive, using a Global variable set as 'password' is recommended",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "env_set",
                "types": [
                    "Message"
                ],
                "display_name": "env_set",
                "method": "process_inputs"
            }
        ],
        "description": "Load .env file into env vars"
    },
    {
        "category": "astra_assistants/AssistantsListAssistants",
        "component_name": "List Assistants",
        "inputs": [],
        "outputs": [
            {
                "name": "assistants",
                "types": [
                    "Message"
                ],
                "display_name": "Assistants",
                "method": "process_inputs"
            }
        ],
        "description": "Returns a list of assistant id's"
    },
    {
        "category": "astra_assistants/AssistantsGetAssistantName",
        "component_name": "Get Assistant name",
        "inputs": [
            {
                "name": "env_set",
                "type": "str",
                "display_name": "Environment Set",
                "info": "Dummy input to allow chaining with Dotenv Component.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "assistant_name",
                "types": [
                    "Message"
                ],
                "display_name": "Assistant Name",
                "method": "process_inputs"
            }
        ],
        "description": "Assistant by id"
    },
    {
        "category": "astra_assistants/AssistantsRun",
        "component_name": "Run Assistant",
        "inputs": [
            {
                "name": "assistant_id",
                "type": "str",
                "display_name": "Assistant ID",
                "info": "The ID of the assistant to run. \n\nCan be retrieved using the List Assistants component or created with the Create Assistant component.",
                "required": false
            },
            {
                "name": "env_set",
                "type": "str",
                "display_name": "Environment Set",
                "info": "Dummy input to allow chaining with Dotenv Component.",
                "required": false
            },
            {
                "name": "thread_id",
                "type": "str",
                "display_name": "Thread ID",
                "info": "Thread ID to use with the run. If not provided, a new thread will be created.",
                "required": false
            },
            {
                "name": "user_message",
                "type": "str",
                "display_name": "User Message",
                "info": "User message to pass to the run.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "assistant_response",
                "types": [
                    "Message"
                ],
                "display_name": "Assistant Response",
                "method": "process_inputs"
            }
        ],
        "description": "Executes an Assistant Run against a thread"
    },
    {
        "category": "astra_assistants/AssistantsCreateAssistant",
        "component_name": "Create Assistant",
        "inputs": [
            {
                "name": "env_set",
                "type": "str",
                "display_name": "Environment Set",
                "info": "Dummy input to allow chaining with Dotenv Component.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "assistant_id",
                "types": [
                    "Message"
                ],
                "display_name": "Assistant ID",
                "method": "process_inputs"
            }
        ],
        "description": "Creates an Assistant and returns it's id"
    },
    {
        "category": "astra_assistants/AssistantsCreateThread",
        "component_name": "Create Assistant Thread",
        "inputs": [
            {
                "name": "env_set",
                "type": "str",
                "display_name": "Environment Set",
                "info": "Dummy input to allow chaining with Dotenv Component.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "thread_id",
                "types": [
                    "Message"
                ],
                "display_name": "Thread ID",
                "method": "process_inputs"
            }
        ],
        "description": "Creates a thread and returns the thread id"
    },
    {
        "category": "astra_assistants/GetEnvVar",
        "component_name": "Get env var",
        "inputs": [],
        "outputs": [
            {
                "name": "env_var_value",
                "types": [
                    "Message"
                ],
                "display_name": "Env var value",
                "method": "process_inputs"
            }
        ],
        "description": "Get env var"
    },
    {
        "category": "chains/LLMMathChain",
        "component_name": "LLMMathChain",
        "inputs": [
            {
                "name": "llm",
                "type": "other",
                "display_name": "Language Model",
                "info": "",
                "required": true
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "The input value to pass to the chain.",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "text",
                "types": [
                    "Message"
                ],
                "display_name": "Text",
                "method": "invoke_chain"
            }
        ],
        "description": "Chain that interprets a prompt and executes python code to do math."
    },
    {
        "category": "chains/SQLGenerator",
        "component_name": "Natural Language to SQL",
        "inputs": [
            {
                "name": "db",
                "type": "other",
                "display_name": "SQLDatabase",
                "info": "",
                "required": true
            },
            {
                "name": "llm",
                "type": "other",
                "display_name": "Language Model",
                "info": "",
                "required": true
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "The input value to pass to the chain.",
                "required": true
            },
            {
                "name": "prompt",
                "type": "str",
                "display_name": "Prompt",
                "info": "The prompt must contain `{question}`.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "text",
                "types": [
                    "Message"
                ],
                "display_name": "Text",
                "method": "invoke_chain"
            }
        ],
        "description": "Generate SQL from natural language."
    },
    {
        "category": "chains/RetrievalQA",
        "component_name": "Retrieval QA",
        "inputs": [
            {
                "name": "llm",
                "type": "other",
                "display_name": "Language Model",
                "info": "",
                "required": true
            },
            {
                "name": "memory",
                "type": "other",
                "display_name": "Memory",
                "info": "",
                "required": false
            },
            {
                "name": "retriever",
                "type": "other",
                "display_name": "Retriever",
                "info": "",
                "required": true
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "The input value to pass to the chain.",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "text",
                "types": [
                    "Message"
                ],
                "display_name": "Text",
                "method": "invoke_chain"
            }
        ],
        "description": "Chain for question-answering querying sources from a retriever."
    },
    {
        "category": "chains/LLMCheckerChain",
        "component_name": "LLMCheckerChain",
        "inputs": [
            {
                "name": "llm",
                "type": "other",
                "display_name": "Language Model",
                "info": "",
                "required": true
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "The input value to pass to the chain.",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "text",
                "types": [
                    "Message"
                ],
                "display_name": "Text",
                "method": "invoke_chain"
            }
        ],
        "description": "Chain for question-answering with self-verification."
    },
    {
        "category": "chains/ConversationChain",
        "component_name": "ConversationChain",
        "inputs": [
            {
                "name": "llm",
                "type": "other",
                "display_name": "Language Model",
                "info": "",
                "required": true
            },
            {
                "name": "memory",
                "type": "other",
                "display_name": "Memory",
                "info": "",
                "required": false
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "The input value to pass to the chain.",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "text",
                "types": [
                    "Message"
                ],
                "display_name": "Text",
                "method": "invoke_chain"
            }
        ],
        "description": "Chain to have a conversation and load context from memory."
    },
    {
        "category": "prompts/LangChain Hub Prompt",
        "component_name": "LangChain Hub",
        "inputs": [
            {
                "name": "langchain_api_key",
                "type": "str",
                "display_name": "Your LangChain API Key",
                "info": "The LangChain API Key to use.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "prompt",
                "types": [
                    "Message"
                ],
                "display_name": "Build Prompt",
                "method": "build_prompt"
            }
        ],
        "description": "Prompt Component that uses LangChain Hub prompts"
    },
    {
        "category": "prompts/Prompt",
        "component_name": "Prompt",
        "inputs": [],
        "outputs": [
            {
                "name": "prompt",
                "types": [
                    "Message"
                ],
                "display_name": "Prompt Message",
                "method": "build_prompt"
            }
        ],
        "description": "Create a prompt template with dynamic variables."
    },
    {
        "category": "documentloaders/Unstructured",
        "component_name": "Unstructured",
        "inputs": [
            {
                "name": "api_key",
                "type": "str",
                "display_name": "Unstructured.io Serverless API Key",
                "info": "Unstructured API Key. Create at: https://app.unstructured.io/",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "data",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "load_documents"
            }
        ],
        "description": "Uses Unstructured.io to extract clean text from raw source documents. Supports: PDF, DOCX, TXT"
    },
    {
        "category": "documentloaders/Confluence",
        "component_name": "Confluence",
        "inputs": [
            {
                "name": "api_key",
                "type": "str",
                "display_name": "API Key",
                "info": "Atlassian Key. Create at: https://id.atlassian.com/manage-profile/security/api-tokens",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "data",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "load_documents"
            }
        ],
        "description": "Confluence wiki collaboration platform"
    },
    {
        "category": "documentloaders/GitLoader",
        "component_name": "GitLoader",
        "inputs": [
            {
                "name": "branch",
                "type": "str",
                "display_name": "Branch",
                "info": "The branch to load files from. Defaults to 'main'.",
                "required": false
            },
            {
                "name": "clone_url",
                "type": "str",
                "display_name": "Clone URL",
                "info": "The URL to clone the Git repository from.",
                "required": false
            },
            {
                "name": "content_filter",
                "type": "str",
                "display_name": "Content Filter",
                "info": "A regex pattern to filter files based on their content.",
                "required": false
            },
            {
                "name": "file_filter",
                "type": "str",
                "display_name": "File Filter",
                "info": "A list of patterns to filter files. Example to include only .py files: '*.py'. Example to exclude .py files: '!*.py'. Multiple patterns can be separated by commas.",
                "required": false
            },
            {
                "name": "repo_path",
                "type": "str",
                "display_name": "Repository Path",
                "info": "The local path to the Git repository.",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "data",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "load_documents"
            }
        ],
        "description": "Load files from a Git repository"
    },
    {
        "category": "Notion/NotionSearch",
        "component_name": "Search ",
        "inputs": [
            {
                "name": "notion_secret",
                "type": "str",
                "display_name": "Notion Secret",
                "info": "The Notion integration token.",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "api_run_model",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "run_model"
            },
            {
                "name": "api_build_tool",
                "types": [
                    "Tool"
                ],
                "display_name": "Tool",
                "method": "build_tool"
            }
        ],
        "description": "Searches all pages and databases that have been shared with an integration."
    },
    {
        "category": "Notion/NotionListPages",
        "component_name": "List Pages ",
        "inputs": [
            {
                "name": "notion_secret",
                "type": "str",
                "display_name": "Notion Secret",
                "info": "The Notion integration token.",
                "required": true
            },
            {
                "name": "query_json",
                "type": "str",
                "display_name": "Database query (JSON)",
                "info": "A JSON string containing the filters and sorts that will be used for querying the database. Leave empty for no filters or sorts.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "api_run_model",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "run_model"
            },
            {
                "name": "api_build_tool",
                "types": [
                    "Tool"
                ],
                "display_name": "Tool",
                "method": "build_tool"
            }
        ],
        "description": "Query a Notion database with filtering and sorting. The input should be a JSON string containing the 'filter' and 'sorts' objects. Example input:\n{\"filter\": {\"property\": \"Status\", \"select\": {\"equals\": \"Done\"}}, \"sorts\": [{\"timestamp\": \"created_time\", \"direction\": \"descending\"}]}"
    },
    {
        "category": "Notion/NotionPageUpdate",
        "component_name": "Update Page Property ",
        "inputs": [
            {
                "name": "notion_secret",
                "type": "str",
                "display_name": "Notion Secret",
                "info": "The Notion integration token.",
                "required": true
            },
            {
                "name": "properties",
                "type": "str",
                "display_name": "Properties",
                "info": "The properties to update on the page (as a JSON string or a dictionary).",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "api_run_model",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "run_model"
            },
            {
                "name": "api_build_tool",
                "types": [
                    "Tool"
                ],
                "display_name": "Tool",
                "method": "build_tool"
            }
        ],
        "description": "Update the properties of a Notion page."
    },
    {
        "category": "Notion/NotionPageCreator",
        "component_name": "Create Page ",
        "inputs": [
            {
                "name": "notion_secret",
                "type": "str",
                "display_name": "Notion Secret",
                "info": "The Notion integration token.",
                "required": true
            },
            {
                "name": "properties_json",
                "type": "str",
                "display_name": "Properties (JSON)",
                "info": "The properties of the new page as a JSON string.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "api_run_model",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "run_model"
            },
            {
                "name": "api_build_tool",
                "types": [
                    "Tool"
                ],
                "display_name": "Tool",
                "method": "build_tool"
            }
        ],
        "description": "A component for creating Notion pages."
    },
    {
        "category": "Notion/NotionDatabaseProperties",
        "component_name": "List Database Properties ",
        "inputs": [
            {
                "name": "notion_secret",
                "type": "str",
                "display_name": "Notion Secret",
                "info": "The Notion integration token.",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "api_run_model",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "run_model"
            },
            {
                "name": "api_build_tool",
                "types": [
                    "Tool"
                ],
                "display_name": "Tool",
                "method": "build_tool"
            }
        ],
        "description": "Retrieve properties of a Notion database."
    },
    {
        "category": "Notion/NotionPageContent",
        "component_name": "Page Content Viewer ",
        "inputs": [
            {
                "name": "notion_secret",
                "type": "str",
                "display_name": "Notion Secret",
                "info": "The Notion integration token.",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "api_run_model",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "run_model"
            },
            {
                "name": "api_build_tool",
                "types": [
                    "Tool"
                ],
                "display_name": "Tool",
                "method": "build_tool"
            }
        ],
        "description": "Retrieve the content of a Notion page as plain text."
    },
    {
        "category": "Notion/AddContentToPage",
        "component_name": "Add Content to Page ",
        "inputs": [
            {
                "name": "markdown_text",
                "type": "str",
                "display_name": "Markdown Text",
                "info": "The markdown text to convert to Notion blocks.",
                "required": false
            },
            {
                "name": "notion_secret",
                "type": "str",
                "display_name": "Notion Secret",
                "info": "The Notion integration token.",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "api_run_model",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "run_model"
            },
            {
                "name": "api_build_tool",
                "types": [
                    "Tool"
                ],
                "display_name": "Tool",
                "method": "build_tool"
            }
        ],
        "description": "Convert markdown text to Notion blocks and append them to a Notion page."
    },
    {
        "category": "Notion/NotionUserList",
        "component_name": "List Users ",
        "inputs": [
            {
                "name": "notion_secret",
                "type": "str",
                "display_name": "Notion Secret",
                "info": "The Notion integration token.",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "api_run_model",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": "run_model"
            },
            {
                "name": "api_build_tool",
                "types": [
                    "Tool"
                ],
                "display_name": "Tool",
                "method": "build_tool"
            }
        ],
        "description": "Retrieve users from Notion."
    },
    {
        "category": "agents/JsonAgent",
        "component_name": "JsonAgent",
        "inputs": [
            {
                "name": "llm",
                "type": "other",
                "display_name": "Language Model",
                "info": "",
                "required": true
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "agent",
                "types": [
                    "AgentExecutor"
                ],
                "display_name": "Agent",
                "method": "build_agent"
            },
            {
                "name": "response",
                "types": [
                    "Message"
                ],
                "display_name": "Response",
                "method": "message_response"
            }
        ],
        "description": "Construct a json agent from an LLM and tools."
    },
    {
        "category": "agents/SQLAgent",
        "component_name": "SQLAgent",
        "inputs": [
            {
                "name": "extra_tools",
                "type": "other",
                "display_name": "Extra Tools",
                "info": "",
                "required": false
            },
            {
                "name": "llm",
                "type": "other",
                "display_name": "Language Model",
                "info": "",
                "required": true
            },
            {
                "name": "database_uri",
                "type": "str",
                "display_name": "Database URI",
                "info": "",
                "required": true
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "agent",
                "types": [
                    "AgentExecutor"
                ],
                "display_name": "Agent",
                "method": "build_agent"
            },
            {
                "name": "response",
                "types": [
                    "Message"
                ],
                "display_name": "Response",
                "method": "message_response"
            }
        ],
        "description": "Construct an SQL agent from an LLM and tools."
    },
    {
        "category": "agents/VectorStoreAgent",
        "component_name": "VectorStoreAgent",
        "inputs": [
            {
                "name": "llm",
                "type": "other",
                "display_name": "Language Model",
                "info": "",
                "required": true
            },
            {
                "name": "vectorstore",
                "type": "other",
                "display_name": "Vector Store",
                "info": "",
                "required": true
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "agent",
                "types": [
                    "AgentExecutor"
                ],
                "display_name": "Agent",
                "method": "build_agent"
            },
            {
                "name": "response",
                "types": [
                    "Message"
                ],
                "display_name": "Response",
                "method": "message_response"
            }
        ],
        "description": "Construct an agent from a Vector Store."
    },
    {
        "category": "agents/HierarchicalCrewComponent",
        "component_name": "Hierarchical Crew",
        "inputs": [
            {
                "name": "agents",
                "type": "other",
                "display_name": "Agents",
                "info": "",
                "required": false
            },
            {
                "name": "function_calling_llm",
                "type": "other",
                "display_name": "Function Calling LLM",
                "info": "Turns the ReAct CrewAI agent into a function-calling agent",
                "required": false
            },
            {
                "name": "manager_agent",
                "type": "other",
                "display_name": "Manager Agent",
                "info": "",
                "required": false
            },
            {
                "name": "manager_llm",
                "type": "other",
                "display_name": "Manager LLM",
                "info": "",
                "required": false
            },
            {
                "name": "tasks",
                "type": "other",
                "display_name": "Tasks",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "output",
                "types": [
                    "Message"
                ],
                "display_name": "Output",
                "method": "build_output"
            }
        ],
        "description": "Represents a group of agents, defining how they should collaborate and the tasks they should perform."
    },
    {
        "category": "agents/CrewAIAgentComponent",
        "component_name": "CrewAI Agent",
        "inputs": [
            {
                "name": "llm",
                "type": "other",
                "display_name": "Language Model",
                "info": "Language model that will run the agent.",
                "required": false
            },
            {
                "name": "tools",
                "type": "other",
                "display_name": "Tools",
                "info": "Tools at agents disposal",
                "required": false
            },
            {
                "name": "backstory",
                "type": "str",
                "display_name": "Backstory",
                "info": "The backstory of the agent.",
                "required": false
            },
            {
                "name": "goal",
                "type": "str",
                "display_name": "Goal",
                "info": "The objective of the agent.",
                "required": false
            },
            {
                "name": "role",
                "type": "str",
                "display_name": "Role",
                "info": "The role of the agent.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "output",
                "types": [
                    "Agent"
                ],
                "display_name": "Agent",
                "method": "build_output"
            }
        ],
        "description": "Represents an agent of CrewAI."
    },
    {
        "category": "agents/XMLAgent",
        "component_name": "XML Agent",
        "inputs": [
            {
                "name": "llm",
                "type": "other",
                "display_name": "Language Model",
                "info": "",
                "required": true
            },
            {
                "name": "tools",
                "type": "other",
                "display_name": "Tools",
                "info": "",
                "required": false
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            },
            {
                "name": "user_prompt",
                "type": "str",
                "display_name": "Prompt",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "agent",
                "types": [
                    "AgentExecutor"
                ],
                "display_name": "Agent",
                "method": "build_agent"
            },
            {
                "name": "response",
                "types": [
                    "Message"
                ],
                "display_name": "Response",
                "method": "message_response"
            }
        ],
        "description": "Agent that uses tools formatting instructions as xml to the Language Model."
    },
    {
        "category": "agents/ToolCallingAgent",
        "component_name": "Tool Calling Agent",
        "inputs": [
            {
                "name": "chat_history",
                "type": "other",
                "display_name": "Chat History",
                "info": "",
                "required": false
            },
            {
                "name": "llm",
                "type": "other",
                "display_name": "Language Model",
                "info": "",
                "required": true
            },
            {
                "name": "tools",
                "type": "other",
                "display_name": "Tools",
                "info": "",
                "required": false
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            },
            {
                "name": "system_prompt",
                "type": "str",
                "display_name": "System Prompt",
                "info": "System prompt for the agent.",
                "required": false
            },
            {
                "name": "user_prompt",
                "type": "str",
                "display_name": "Prompt",
                "info": "This prompt must contain 'input' key.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "agent",
                "types": [
                    "AgentExecutor"
                ],
                "display_name": "Agent",
                "method": "build_agent"
            },
            {
                "name": "response",
                "types": [
                    "Message"
                ],
                "display_name": "Response",
                "method": "message_response"
            }
        ],
        "description": "Agent that uses tools"
    },
    {
        "category": "agents/OpenAPIAgent",
        "component_name": "OpenAPI Agent",
        "inputs": [
            {
                "name": "llm",
                "type": "other",
                "display_name": "Language Model",
                "info": "",
                "required": true
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "agent",
                "types": [
                    "AgentExecutor"
                ],
                "display_name": "Agent",
                "method": "build_agent"
            },
            {
                "name": "response",
                "types": [
                    "Message"
                ],
                "display_name": "Response",
                "method": "message_response"
            }
        ],
        "description": "Agent to interact with OpenAPI API."
    },
    {
        "category": "agents/SequentialTaskAgentComponent",
        "component_name": "Sequential Task Agent",
        "inputs": [
            {
                "name": "llm",
                "type": "other",
                "display_name": "Language Model",
                "info": "Language model that will run the agent.",
                "required": false
            },
            {
                "name": "previous_task",
                "type": "other",
                "display_name": "Previous Task",
                "info": "The previous task in the sequence (for chaining).",
                "required": false
            },
            {
                "name": "tools",
                "type": "other",
                "display_name": "Tools",
                "info": "Tools at agent's disposal",
                "required": false
            },
            {
                "name": "backstory",
                "type": "str",
                "display_name": "Backstory",
                "info": "The backstory of the agent.",
                "required": false
            },
            {
                "name": "expected_output",
                "type": "str",
                "display_name": "Expected Task Output",
                "info": "Clear definition of expected task outcome.",
                "required": false
            },
            {
                "name": "goal",
                "type": "str",
                "display_name": "Goal",
                "info": "The objective of the agent.",
                "required": false
            },
            {
                "name": "role",
                "type": "str",
                "display_name": "Role",
                "info": "The role of the agent.",
                "required": false
            },
            {
                "name": "task_description",
                "type": "str",
                "display_name": "Task Description",
                "info": "Descriptive text detailing task's purpose and execution.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "task_output",
                "types": [
                    "SequentialTask"
                ],
                "display_name": "Sequential Task",
                "method": "build_agent_and_task"
            }
        ],
        "description": "Creates a CrewAI Task and its associated Agent."
    },
    {
        "category": "agents/CSVAgent",
        "component_name": "CSVAgent",
        "inputs": [
            {
                "name": "llm",
                "type": "other",
                "display_name": "Language Model",
                "info": "An LLM Model Object (It can be found in any LLM Component).",
                "required": true
            },
            {
                "name": "path",
                "type": "file",
                "display_name": "File Path",
                "info": "A CSV File or File Path.",
                "required": true
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Text",
                "info": "Text to be passed as input and extract info from the CSV File.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "response",
                "types": [
                    "Message"
                ],
                "display_name": "Response",
                "method": "build_agent_response"
            },
            {
                "name": "agent",
                "types": [
                    "AgentExecutor"
                ],
                "display_name": "Agent",
                "method": "build_agent"
            }
        ],
        "description": "Construct a CSV agent from a CSV and tools."
    },
    {
        "category": "agents/VectorStoreRouterAgent",
        "component_name": "VectorStoreRouterAgent",
        "inputs": [
            {
                "name": "llm",
                "type": "other",
                "display_name": "Language Model",
                "info": "",
                "required": true
            },
            {
                "name": "vectorstores",
                "type": "other",
                "display_name": "Vector Stores",
                "info": "",
                "required": true
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "agent",
                "types": [
                    "AgentExecutor"
                ],
                "display_name": "Agent",
                "method": "build_agent"
            },
            {
                "name": "response",
                "types": [
                    "Message"
                ],
                "display_name": "Response",
                "method": "message_response"
            }
        ],
        "description": "Construct an agent from a Vector Store Router."
    },
    {
        "category": "agents/OpenAIToolsAgent",
        "component_name": "OpenAI Tools Agent",
        "inputs": [
            {
                "name": "chat_history",
                "type": "other",
                "display_name": "Chat History",
                "info": "",
                "required": false
            },
            {
                "name": "llm",
                "type": "other",
                "display_name": "Language Model",
                "info": "",
                "required": true
            },
            {
                "name": "tools",
                "type": "other",
                "display_name": "Tools",
                "info": "",
                "required": false
            },
            {
                "name": "input_value",
                "type": "str",
                "display_name": "Input",
                "info": "",
                "required": false
            },
            {
                "name": "system_prompt",
                "type": "str",
                "display_name": "System Prompt",
                "info": "System prompt for the agent.",
                "required": false
            },
            {
                "name": "user_prompt",
                "type": "str",
                "display_name": "Prompt",
                "info": "This prompt must contain 'input' key.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "agent",
                "types": [
                    "AgentExecutor"
                ],
                "display_name": "Agent",
                "method": "build_agent"
            },
            {
                "name": "response",
                "types": [
                    "Message"
                ],
                "display_name": "Response",
                "method": "message_response"
            }
        ],
        "description": "Agent that uses tools via openai-tools."
    },
    {
        "category": "agents/SequentialCrewComponent",
        "component_name": "Sequential Crew",
        "inputs": [
            {
                "name": "function_calling_llm",
                "type": "other",
                "display_name": "Function Calling LLM",
                "info": "Turns the ReAct CrewAI agent into a function-calling agent",
                "required": false
            },
            {
                "name": "tasks",
                "type": "other",
                "display_name": "Tasks",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "output",
                "types": [
                    "Message"
                ],
                "display_name": "Output",
                "method": "build_output"
            }
        ],
        "description": "Represents a group of agents with tasks that are executed sequentially."
    },
    {
        "category": "langchain_utilities/FirecrawlScrapeApi",
        "component_name": "FirecrawlScrapeApi",
        "inputs": [
            {
                "name": "api_key",
                "type": "str",
                "display_name": "API Key",
                "info": "The API key to use Firecrawl API.",
                "required": true
            },
            {
                "name": "url",
                "type": "str",
                "display_name": "URL",
                "info": "The URL to scrape.",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "data",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": null
            }
        ],
        "description": "Firecrawl Scrape API."
    },
    {
        "category": "langchain_utilities/SQLDatabase",
        "component_name": "SQLDatabase",
        "inputs": [
            {
                "name": "uri",
                "type": "str",
                "display_name": "URI",
                "info": "URI to the database.",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "sqldatabase",
                "types": [
                    "SQLDatabase"
                ],
                "display_name": "SQLDatabase",
                "method": null
            }
        ],
        "description": "SQL Database"
    },
    {
        "category": "langchain_utilities/FirecrawlCrawlApi",
        "component_name": "FirecrawlCrawlApi",
        "inputs": [
            {
                "name": "api_key",
                "type": "str",
                "display_name": "API Key",
                "info": "The API key to use Firecrawl API.",
                "required": true
            },
            {
                "name": "idempotency_key",
                "type": "str",
                "display_name": "Idempotency Key",
                "info": "Optional idempotency key to ensure unique requests.",
                "required": false
            },
            {
                "name": "url",
                "type": "str",
                "display_name": "URL",
                "info": "The base URL to start crawling from.",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "data",
                "types": [
                    "Data"
                ],
                "display_name": "Data",
                "method": null
            }
        ],
        "description": "Firecrawl Crawl API."
    },
    {
        "category": "langchain_utilities/SpiderTool",
        "component_name": "Spider Web Crawler & Scraper",
        "inputs": [
            {
                "name": "spider_api_key",
                "type": "str",
                "display_name": "Spider API Key",
                "info": "The Spider API Key, get it from https://spider.cloud",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "content",
                "types": [
                    "Data"
                ],
                "display_name": "Markdown",
                "method": "crawl"
            }
        ],
        "description": "Spider API for web crawling and scraping."
    },
    {
        "category": "langchain_utilities/JSONDocumentBuilder",
        "component_name": "JSON Document Builder",
        "inputs": [
            {
                "name": "key",
                "type": "str",
                "display_name": "Key",
                "info": "",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "document",
                "types": [
                    "Document"
                ],
                "display_name": "Document",
                "method": null
            }
        ],
        "description": "Build a Document containing a JSON object using a key and another Document page content."
    },
    {
        "category": "retrievers/CohereRerank",
        "component_name": "Cohere Rerank",
        "inputs": [
            {
                "name": "retriever",
                "type": "other",
                "display_name": "Retriever",
                "info": "",
                "required": false
            },
            {
                "name": "api_key",
                "type": "str",
                "display_name": "API Key",
                "info": "",
                "required": false
            },
            {
                "name": "search_query",
                "type": "str",
                "display_name": "Search Query",
                "info": "",
                "required": false
            },
            {
                "name": "user_agent",
                "type": "str",
                "display_name": "User Agent",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "base_retriever",
                "types": [
                    "Retriever"
                ],
                "display_name": "Retriever",
                "method": "build_base_retriever"
            },
            {
                "name": "search_results",
                "types": [
                    "Data"
                ],
                "display_name": "Search Results",
                "method": "search_documents"
            }
        ],
        "description": "Rerank documents using the Cohere API and a retriever."
    },
    {
        "category": "retrievers/MetalRetriever",
        "component_name": "Metal Retriever",
        "inputs": [
            {
                "name": "api_key",
                "type": "str",
                "display_name": "API Key",
                "info": "",
                "required": true
            },
            {
                "name": "client_id",
                "type": "str",
                "display_name": "Client ID",
                "info": "",
                "required": true
            },
            {
                "name": "index_id",
                "type": "str",
                "display_name": "Index ID",
                "info": "",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "retriever",
                "types": [
                    "Retriever"
                ],
                "display_name": "Retriever",
                "method": null
            }
        ],
        "description": "Retriever that uses the Metal API."
    },
    {
        "category": "retrievers/MultiQueryRetriever",
        "component_name": "MultiQueryRetriever",
        "inputs": [
            {
                "name": "prompt",
                "type": "Text",
                "display_name": "Prompt",
                "info": "",
                "required": false
            },
            {
                "name": "parser_key",
                "type": "str",
                "display_name": "Parser Key",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "multiqueryretriever",
                "types": [
                    "MultiQueryRetriever"
                ],
                "display_name": "MultiQueryRetriever",
                "method": null
            }
        ],
        "description": "Initialize from llm using default template."
    },
    {
        "category": "retrievers/AmazonKendra",
        "component_name": "Amazon Kendra Retriever",
        "inputs": [
            {
                "name": "credentials_profile_name",
                "type": "str",
                "display_name": "Credentials Profile Name",
                "info": "",
                "required": false
            },
            {
                "name": "index_id",
                "type": "str",
                "display_name": "Index ID",
                "info": "",
                "required": true
            },
            {
                "name": "region_name",
                "type": "str",
                "display_name": "Region Name",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "retriever",
                "types": [
                    "Retriever"
                ],
                "display_name": "Retriever",
                "method": null
            }
        ],
        "description": "Retriever that uses the Amazon Kendra API."
    },
    {
        "category": "retrievers/NvidiaRerankComponent",
        "component_name": "NVIDIA Rerank",
        "inputs": [
            {
                "name": "retriever",
                "type": "other",
                "display_name": "Retriever",
                "info": "",
                "required": false
            },
            {
                "name": "api_key",
                "type": "str",
                "display_name": "API Key",
                "info": "",
                "required": false
            },
            {
                "name": "search_query",
                "type": "str",
                "display_name": "Search Query",
                "info": "",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "base_retriever",
                "types": [
                    "Retriever"
                ],
                "display_name": "Retriever",
                "method": "build_base_retriever"
            },
            {
                "name": "search_results",
                "types": [
                    "Data"
                ],
                "display_name": "Search Results",
                "method": "search_documents"
            }
        ],
        "description": "Rerank documents using the NVIDIA API and a retriever."
    },
    {
        "category": "retrievers/VectaraSelfQueryRetriver",
        "component_name": "Vectara Self Query Retriever for Vectara Vector Store",
        "inputs": [
            {
                "name": "document_content_description",
                "type": "str",
                "display_name": "Document Content Description",
                "info": "For self query retriever",
                "required": true
            },
            {
                "name": "metadata_field_info",
                "type": "str",
                "display_name": "Metadata Field Info",
                "info": "Each metadata field info is a string in the form of key value pair dictionary containing additional search metadata.\nExample input: {\"name\":\"speech\",\"description\":\"what name of the speech\",\"type\":\"string or list[string]\"}.\nThe keys should remain constant(name, description, type)",
                "required": true
            }
        ],
        "outputs": [
            {
                "name": "retriever",
                "types": [
                    "Retriever"
                ],
                "display_name": "Retriever",
                "method": null
            }
        ],
        "description": "Implementation of Vectara Self Query Retriever"
    },
    {
        "category": "retrievers/SelfQueryRetriever",
        "component_name": "Self Query Retriever",
        "inputs": [
            {
                "name": "attribute_infos",
                "type": "other",
                "display_name": "Metadata Field Info",
                "info": "Metadata Field Info to be passed as input.",
                "required": false
            },
            {
                "name": "llm",
                "type": "other",
                "display_name": "LLM",
                "info": "LLM to be passed as input.",
                "required": false
            },
            {
                "name": "query",
                "type": "other",
                "display_name": "Query",
                "info": "Query to be passed as input.",
                "required": false
            },
            {
                "name": "vectorstore",
                "type": "other",
                "display_name": "Vector Store",
                "info": "Vector Store to be passed as input.",
                "required": false
            },
            {
                "name": "document_content_description",
                "type": "str",
                "display_name": "Document Content Description",
                "info": "Document Content Description to be passed as input.",
                "required": false
            }
        ],
        "outputs": [
            {
                "name": "documents",
                "types": [
                    "Data"
                ],
                "display_name": "Retrieved Documents",
                "method": "retrieve_documents"
            }
        ],
        "description": "Retriever that uses a vector store and an LLM to generate the vector store queries."
    },
    {
        "category": "retrievers/VectorStoreRetriever",
        "component_name": "VectorStore Retriever",
        "inputs": [],
        "outputs": [
            {
                "name": "vectorstoreretriever",
                "types": [
                    "VectorStoreRetriever"
                ],
                "display_name": "VectorStoreRetriever",
                "method": null
            }
        ],
        "description": "A vector store retriever"
    }
    ```

    """

    class Config:
        schema_extra = {
            "examples": [
                {
                    "data": {
                        "edges": [
                            {
                                "className": "",
                                "data": {
                                    "sourceHandle": {
                                        "dataType": "ChatInput",
                                        "id": "ChatInput-DFgo2",
                                        "name": "message",
                                        "output_types": [
                                            "Message"
                                        ]
                                    },
                                    "targetHandle": {
                                        "fieldName": "search_input",
                                        "id": "AstraVectorStoreComponent-XE3MH",
                                        "inputTypes": [
                                            "Message"
                                        ],
                                        "type": "str"
                                    }
                                },
                                "id": "reactflow__edge-ChatInput-DFgo2{œdataTypeœ:œChatInputœ,œidœ:œChatInput-DFgo2œ,œnameœ:œmessageœ,œoutput_typesœ:[œMessageœ]}-AstraVectorStoreComponent-XE3MH{œfieldNameœ:œsearch_inputœ,œidœ:œAstraVectorStoreComponent-XE3MHœ,œinputTypesœ:[œMessageœ],œtypeœ:œstrœ}",
                                "source": "ChatInput-DFgo2",
                                "sourceHandle": "{œdataTypeœ: œChatInputœ, œidœ: œChatInput-DFgo2œ, œnameœ: œmessageœ, œoutput_typesœ: [œMessageœ]}",
                                "target": "AstraVectorStoreComponent-XE3MH",
                                "targetHandle": "{œfieldNameœ: œsearch_inputœ, œidœ: œAstraVectorStoreComponent-XE3MHœ, œinputTypesœ: [œMessageœ], œtypeœ: œstrœ}"
                            },
                            {
                                "className": "",
                                "data": {
                                    "sourceHandle": {
                                        "dataType": "ParseData",
                                        "id": "ParseData-ILuxa",
                                        "name": "text",
                                        "output_types": [
                                            "Message"
                                        ]
                                    },
                                    "targetHandle": {
                                        "fieldName": "context",
                                        "id": "Prompt-Tfriy",
                                        "inputTypes": [
                                            "Message",
                                            "Text"
                                        ],
                                        "type": "str"
                                    }
                                },
                                "id": "reactflow__edge-ParseData-ILuxa{œdataTypeœ:œParseDataœ,œidœ:œParseData-ILuxaœ,œnameœ:œtextœ,œoutput_typesœ:[œMessageœ]}-Prompt-Tfriy{œfieldNameœ:œcontextœ,œidœ:œPrompt-Tfriyœ,œinputTypesœ:[œMessageœ,œTextœ],œtypeœ:œstrœ}",
                                "source": "ParseData-ILuxa",
                                "sourceHandle": "{œdataTypeœ: œParseDataœ, œidœ: œParseData-ILuxaœ, œnameœ: œtextœ, œoutput_typesœ: [œMessageœ]}",
                                "target": "Prompt-Tfriy",
                                "targetHandle": "{œfieldNameœ: œcontextœ, œidœ: œPrompt-Tfriyœ, œinputTypesœ: [œMessageœ, œTextœ], œtypeœ: œstrœ}"
                            },
                            {
                                "className": "",
                                "data": {
                                    "sourceHandle": {
                                        "dataType": "ChatInput",
                                        "id": "ChatInput-DFgo2",
                                        "name": "message",
                                        "output_types": [
                                            "Message"
                                        ]
                                    },
                                    "targetHandle": {
                                        "fieldName": "question",
                                        "id": "Prompt-Tfriy",
                                        "inputTypes": [
                                            "Message",
                                            "Text"
                                        ],
                                        "type": "str"
                                    }
                                },
                                "id": "reactflow__edge-ChatInput-DFgo2{œdataTypeœ:œChatInputœ,œidœ:œChatInput-DFgo2œ,œnameœ:œmessageœ,œoutput_typesœ:[œMessageœ]}-Prompt-Tfriy{œfieldNameœ:œquestionœ,œidœ:œPrompt-Tfriyœ,œinputTypesœ:[œMessageœ,œTextœ],œtypeœ:œstrœ}",
                                "source": "ChatInput-DFgo2",
                                "sourceHandle": "{œdataTypeœ: œChatInputœ, œidœ: œChatInput-DFgo2œ, œnameœ: œmessageœ, œoutput_typesœ: [œMessageœ]}",
                                "target": "Prompt-Tfriy",
                                "targetHandle": "{œfieldNameœ: œquestionœ, œidœ: œPrompt-Tfriyœ, œinputTypesœ: [œMessageœ, œTextœ], œtypeœ: œstrœ}"
                            },
                            {
                                "className": "",
                                "data": {
                                    "sourceHandle": {
                                        "dataType": "File",
                                        "id": "File-TBV93",
                                        "name": "data",
                                        "output_types": [
                                            "Data"
                                        ]
                                    },
                                    "targetHandle": {
                                        "fieldName": "data_inputs",
                                        "id": "SplitText-rAbUh",
                                        "inputTypes": [
                                            "Data"
                                        ],
                                        "type": "other"
                                    }
                                },
                                "id": "reactflow__edge-File-TBV93{œdataTypeœ:œFileœ,œidœ:œFile-TBV93œ,œnameœ:œdataœ,œoutput_typesœ:[œDataœ]}-SplitText-rAbUh{œfieldNameœ:œdata_inputsœ,œidœ:œSplitText-rAbUhœ,œinputTypesœ:[œDataœ],œtypeœ:œotherœ}",
                                "source": "File-TBV93",
                                "sourceHandle": "{œdataTypeœ: œFileœ, œidœ: œFile-TBV93œ, œnameœ: œdataœ, œoutput_typesœ: [œDataœ]}",
                                "target": "SplitText-rAbUh",
                                "targetHandle": "{œfieldNameœ: œdata_inputsœ, œidœ: œSplitText-rAbUhœ, œinputTypesœ: [œDataœ], œtypeœ: œotherœ}"
                            },
                            {
                                "className": "",
                                "data": {
                                    "sourceHandle": {
                                        "dataType": "SplitText",
                                        "id": "SplitText-rAbUh",
                                        "name": "chunks",
                                        "output_types": [
                                            "Data"
                                        ]
                                    },
                                    "targetHandle": {
                                        "fieldName": "ingest_data",
                                        "id": "AstraVectorStoreComponent-6hNSy",
                                        "inputTypes": [
                                            "Data"
                                        ],
                                        "type": "other"
                                    }
                                },
                                "id": "reactflow__edge-SplitText-rAbUh{œdataTypeœ:œSplitTextœ,œidœ:œSplitText-rAbUhœ,œnameœ:œchunksœ,œoutput_typesœ:[œDataœ]}-AstraVectorStoreComponent-6hNSy{œfieldNameœ:œingest_dataœ,œidœ:œAstraVectorStoreComponent-6hNSyœ,œinputTypesœ:[œDataœ],œtypeœ:œotherœ}",
                                "source": "SplitText-rAbUh",
                                "sourceHandle": "{œdataTypeœ: œSplitTextœ, œidœ: œSplitText-rAbUhœ, œnameœ: œchunksœ, œoutput_typesœ: [œDataœ]}",
                                "target": "AstraVectorStoreComponent-6hNSy",
                                "targetHandle": "{œfieldNameœ: œingest_dataœ, œidœ: œAstraVectorStoreComponent-6hNSyœ, œinputTypesœ: [œDataœ], œtypeœ: œotherœ}"
                            },
                            {
                                "className": "",
                                "data": {
                                    "sourceHandle": {
                                        "dataType": "OpenAIEmbeddings",
                                        "id": "OpenAIEmbeddings-hLfqb",
                                        "name": "embeddings",
                                        "output_types": [
                                            "Embeddings"
                                        ]
                                    },
                                    "targetHandle": {
                                        "fieldName": "embedding",
                                        "id": "AstraVectorStoreComponent-6hNSy",
                                        "inputTypes": [
                                            "Embeddings",
                                            "dict"
                                        ],
                                        "type": "other"
                                    }
                                },
                                "id": "reactflow__edge-OpenAIEmbeddings-hLfqb{œdataTypeœ:œOpenAIEmbeddingsœ,œidœ:œOpenAIEmbeddings-hLfqbœ,œnameœ:œembeddingsœ,œoutput_typesœ:[œEmbeddingsœ]}-AstraVectorStoreComponent-6hNSy{œfieldNameœ:œembeddingœ,œidœ:œAstraVectorStoreComponent-6hNSyœ,œinputTypesœ:[œEmbeddingsœ,œdictœ],œtypeœ:œotherœ}",
                                "source": "OpenAIEmbeddings-hLfqb",
                                "sourceHandle": "{œdataTypeœ: œOpenAIEmbeddingsœ, œidœ: œOpenAIEmbeddings-hLfqbœ, œnameœ: œembeddingsœ, œoutput_typesœ: [œEmbeddingsœ]}",
                                "target": "AstraVectorStoreComponent-6hNSy",
                                "targetHandle": "{œfieldNameœ: œembeddingœ, œidœ: œAstraVectorStoreComponent-6hNSyœ, œinputTypesœ: [œEmbeddingsœ, œdictœ], œtypeœ: œotherœ}"
                            },
                            {
                                "className": "",
                                "data": {
                                    "sourceHandle": {
                                        "dataType": "OpenAIEmbeddings",
                                        "id": "OpenAIEmbeddings-OhWJM",
                                        "name": "embeddings",
                                        "output_types": [
                                            "Embeddings"
                                        ]
                                    },
                                    "targetHandle": {
                                        "fieldName": "embedding",
                                        "id": "AstraVectorStoreComponent-XE3MH",
                                        "inputTypes": [
                                            "Embeddings",
                                            "dict"
                                        ],
                                        "type": "other"
                                    }
                                },
                                "id": "reactflow__edge-OpenAIEmbeddings-OhWJM{œdataTypeœ:œOpenAIEmbeddingsœ,œidœ:œOpenAIEmbeddings-OhWJMœ,œnameœ:œembeddingsœ,œoutput_typesœ:[œEmbeddingsœ]}-AstraVectorStoreComponent-XE3MH{œfieldNameœ:œembeddingœ,œidœ:œAstraVectorStoreComponent-XE3MHœ,œinputTypesœ:[œEmbeddingsœ,œdictœ],œtypeœ:œotherœ}",
                                "source": "OpenAIEmbeddings-OhWJM",
                                "sourceHandle": "{œdataTypeœ: œOpenAIEmbeddingsœ, œidœ: œOpenAIEmbeddings-OhWJMœ, œnameœ: œembeddingsœ, œoutput_typesœ: [œEmbeddingsœ]}",
                                "target": "AstraVectorStoreComponent-XE3MH",
                                "targetHandle": "{œfieldNameœ: œembeddingœ, œidœ: œAstraVectorStoreComponent-XE3MHœ, œinputTypesœ: [œEmbeddingsœ, œdictœ], œtypeœ: œotherœ}"
                            },
                            {
                                "className": "",
                                "data": {
                                    "sourceHandle": {
                                        "dataType": "Prompt",
                                        "id": "Prompt-Tfriy",
                                        "name": "prompt",
                                        "output_types": [
                                            "Message"
                                        ]
                                    },
                                    "targetHandle": {
                                        "fieldName": "input_value",
                                        "id": "OpenAIModel-ExXPZ",
                                        "inputTypes": [
                                            "Message"
                                        ],
                                        "type": "str"
                                    }
                                },
                                "id": "reactflow__edge-Prompt-Tfriy{œdataTypeœ:œPromptœ,œidœ:œPrompt-Tfriyœ,œnameœ:œpromptœ,œoutput_typesœ:[œMessageœ]}-OpenAIModel-ExXPZ{œfieldNameœ:œinput_valueœ,œidœ:œOpenAIModel-ExXPZœ,œinputTypesœ:[œMessageœ],œtypeœ:œstrœ}",
                                "source": "Prompt-Tfriy",
                                "sourceHandle": "{œdataTypeœ: œPromptœ, œidœ: œPrompt-Tfriyœ, œnameœ: œpromptœ, œoutput_typesœ: [œMessageœ]}",
                                "target": "OpenAIModel-ExXPZ",
                                "targetHandle": "{œfieldNameœ: œinput_valueœ, œidœ: œOpenAIModel-ExXPZœ, œinputTypesœ: [œMessageœ], œtypeœ: œstrœ}"
                            },
                            {
                                "className": "",
                                "data": {
                                    "sourceHandle": {
                                        "dataType": "OpenAIModel",
                                        "id": "OpenAIModel-ExXPZ",
                                        "name": "text_output",
                                        "output_types": [
                                            "Message"
                                        ]
                                    },
                                    "targetHandle": {
                                        "fieldName": "input_value",
                                        "id": "ChatOutput-Mh7FA",
                                        "inputTypes": [
                                            "Message"
                                        ],
                                        "type": "str"
                                    }
                                },
                                "id": "reactflow__edge-OpenAIModel-ExXPZ{œdataTypeœ:œOpenAIModelœ,œidœ:œOpenAIModel-ExXPZœ,œnameœ:œtext_outputœ,œoutput_typesœ:[œMessageœ]}-ChatOutput-Mh7FA{œfieldNameœ:œinput_valueœ,œidœ:œChatOutput-Mh7FAœ,œinputTypesœ:[œMessageœ],œtypeœ:œstrœ}",
                                "source": "OpenAIModel-ExXPZ",
                                "sourceHandle": "{œdataTypeœ: œOpenAIModelœ, œidœ: œOpenAIModel-ExXPZœ, œnameœ: œtext_outputœ, œoutput_typesœ: [œMessageœ]}",
                                "target": "ChatOutput-Mh7FA",
                                "targetHandle": "{œfieldNameœ: œinput_valueœ, œidœ: œChatOutput-Mh7FAœ, œinputTypesœ: [œMessageœ], œtypeœ: œstrœ}"
                            },
                            {
                                "className": "",
                                "data": {
                                    "sourceHandle": {
                                        "dataType": "AstraVectorStoreComponent",
                                        "id": "AstraVectorStoreComponent-XE3MH",
                                        "name": "search_results",
                                        "output_types": [
                                            "Data"
                                        ]
                                    },
                                    "targetHandle": {
                                        "fieldName": "data",
                                        "id": "ParseData-ILuxa",
                                        "inputTypes": [
                                            "Data"
                                        ],
                                        "type": "other"
                                    }
                                },
                                "id": "reactflow__edge-AstraVectorStoreComponent-XE3MH{œdataTypeœ:œAstraVectorStoreComponentœ,œidœ:œAstraVectorStoreComponent-XE3MHœ,œnameœ:œsearch_resultsœ,œoutput_typesœ:[œDataœ]}-ParseData-ILuxa{œfieldNameœ:œdataœ,œidœ:œParseData-ILuxaœ,œinputTypesœ:[œDataœ],œtypeœ:œotherœ}",
                                "source": "AstraVectorStoreComponent-XE3MH",
                                "sourceHandle": "{œdataTypeœ: œAstraVectorStoreComponentœ, œidœ: œAstraVectorStoreComponent-XE3MHœ, œnameœ: œsearch_resultsœ, œoutput_typesœ: [œDataœ]}",
                                "target": "ParseData-ILuxa",
                                "targetHandle": "{œfieldNameœ: œdataœ, œidœ: œParseData-ILuxaœ, œinputTypesœ: [œDataœ], œtypeœ: œotherœ}"
                            }
                        ],
                        "nodes": [
                            {
                                "data": {
                                    "description": "Get chat inputs from the Playground.",
                                    "display_name": "Chat Input",
                                    "id": "ChatInput-DFgo2",
                                    "node": {
                                        "base_classes": [
                                            "Message"
                                        ],
                                        "beta": False,
                                        "conditional_paths": [],
                                        "custom_fields": {},
                                        "description": "Get chat inputs from the Playground.",
                                        "display_name": "Chat Input",
                                        "documentation": "",
                                        "edited": False,
                                        "field_order": [
                                            "input_value",
                                            "should_store_message",
                                            "sender",
                                            "sender_name",
                                            "session_id",
                                            "files"
                                        ],
                                        "frozen": False,
                                        "icon": "ChatInput",
                                        "output_types": [],
                                        "outputs": [
                                            {
                                                "cache": True,
                                                "display_name": "Message",
                                                "method": "message_response",
                                                "name": "message",
                                                "selected": "Message",
                                                "types": [
                                                    "Message"
                                                ],
                                                "value": "__UNDEFINED__"
                                            }
                                        ],
                                        "pinned": False,
                                        "template": {
                                            "_type": "Component",
                                            "code": {
                                                "advanced": True,
                                                "dynamic": True,
                                                "fileTypes": [],
                                                "file_path": "",
                                                "info": "",
                                                "list": False,
                                                "load_from_db": False,
                                                "multiline": True,
                                                "name": "code",
                                                "password": False,
                                                "placeholder": "",
                                                "required": True,
                                                "show": True,
                                                "title_case": False,
                                                "type": "code",
                                                "value": "from langflow.base.data.utils import IMG_FILE_TYPES, TEXT_FILE_TYPES\nfrom langflow.base.io.chat import ChatComponent\nfrom langflow.inputs import BoolInput\nfrom langflow.io import DropdownInput, FileInput, MessageTextInput, MultilineInput, Output\nfrom langflow.memory import store_message\nfrom langflow.schema.message import Message\nfrom langflow.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_USER, MESSAGE_SENDER_NAME_USER\n\n\nclass ChatInput(ChatComponent):\n    display_name = \"Chat Input\"\n    description = \"Get chat inputs from the Playground.\"\n    icon = \"ChatInput\"\n    name = \"ChatInput\"\n\n    inputs = [\n        MultilineInput(\n            name=\"input_value\",\n            display_name=\"Text\",\n            value=\"\",\n            info=\"Message to be passed as input.\",\n        ),\n        BoolInput(\n            name=\"should_store_message\",\n            display_name=\"Store Messages\",\n            info=\"Store the message in the history.\",\n            value=True,\n            advanced=True,\n        ),\n        DropdownInput(\n            name=\"sender\",\n            display_name=\"Sender Type\",\n            options=[MESSAGE_SENDER_AI, MESSAGE_SENDER_USER],\n            value=MESSAGE_SENDER_USER,\n            info=\"Type of sender.\",\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"sender_name\",\n            display_name=\"Sender Name\",\n            info=\"Name of the sender.\",\n            value=MESSAGE_SENDER_NAME_USER,\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"session_id\",\n            display_name=\"Session ID\",\n            info=\"The session ID of the chat. If empty, the current session ID parameter will be used.\",\n            advanced=True,\n        ),\n        FileInput(\n            name=\"files\",\n            display_name=\"Files\",\n            file_types=TEXT_FILE_TYPES + IMG_FILE_TYPES,\n            info=\"Files to be sent with the message.\",\n            advanced=True,\n            is_list=True,\n        ),\n    ]\n    outputs = [\n        Output(display_name=\"Message\", name=\"message\", method=\"message_response\"),\n    ]\n\n    def message_response(self) -> Message:\n        message = Message(\n            text=self.input_value,\n            sender=self.sender,\n            sender_name=self.sender_name,\n            session_id=self.session_id,\n            files=self.files,\n        )\n\n        if (\n            self.session_id\n            and isinstance(message, Message)\n            and isinstance(message.text, str)\n            and self.should_store_message\n        ):\n            store_message(\n                message,\n                flow_id=self.graph.flow_id,\n            )\n            self.message.value = message\n\n        self.status = message\n        return message\n"
                                            },
                                            "files": {
                                                "advanced": True,
                                                "display_name": "Files",
                                                "dynamic": False,
                                                "fileTypes": [
                                                    "txt",
                                                    "md",
                                                    "mdx",
                                                    "csv",
                                                    "json",
                                                    "yaml",
                                                    "yml",
                                                    "xml",
                                                    "html",
                                                    "htm",
                                                    "pdf",
                                                    "docx",
                                                    "py",
                                                    "sh",
                                                    "sql",
                                                    "js",
                                                    "ts",
                                                    "tsx",
                                                    "jpg",
                                                    "jpeg",
                                                    "png",
                                                    "bmp",
                                                    "image"
                                                ],
                                                "file_path": "",
                                                "info": "Files to be sent with the message.",
                                                "list": True,
                                                "name": "files",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "file",
                                                "value": ""
                                            },
                                            "input_value": {
                                                "advanced": False,
                                                "display_name": "Text",
                                                "dynamic": False,
                                                "info": "Message to be passed as input.",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "list": False,
                                                "load_from_db": False,
                                                "multiline": True,
                                                "name": "input_value",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "sender": {
                                                "advanced": True,
                                                "display_name": "Sender Type",
                                                "dynamic": False,
                                                "info": "Type of sender.",
                                                "name": "sender",
                                                "options": [
                                                    "Machine",
                                                    "User"
                                                ],
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": "User"
                                            },
                                            "sender_name": {
                                                "advanced": True,
                                                "display_name": "Sender Name",
                                                "dynamic": False,
                                                "info": "Name of the sender.",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "sender_name",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": "User"
                                            },
                                            "session_id": {
                                                "advanced": True,
                                                "display_name": "Session ID",
                                                "dynamic": False,
                                                "info": "The session ID of the chat. If empty, the current session ID parameter will be used.",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "session_id",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "should_store_message": {
                                                "advanced": True,
                                                "display_name": "Store Messages",
                                                "dynamic": False,
                                                "info": "Store the message in the history.",
                                                "list": False,
                                                "name": "should_store_message",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "bool",
                                                "value": True
                                            }
                                        }
                                    },
                                    "type": "ChatInput"
                                },
                                "dragging": False,
                                "height": 302,
                                "id": "ChatInput-DFgo2",
                                "position": {
                                    "x": 642.3545710150049,
                                    "y": 220.22556606238678
                                },
                                "positionAbsolute": {
                                    "x": 642.3545710150049,
                                    "y": 220.22556606238678
                                },
                                "selected": False,
                                "type": "genericNode",
                                "width": 384
                            },
                            {
                                "data": {
                                    "description": "Implementation of Vector Store using Astra DB with search capabilities",
                                    "display_name": "Astra DB",
                                    "edited": False,
                                    "id": "AstraVectorStoreComponent-XE3MH",
                                    "node": {
                                        "base_classes": [
                                            "Data",
                                            "Retriever"
                                        ],
                                        "beta": False,
                                        "conditional_paths": [],
                                        "custom_fields": {},
                                        "description": "Implementation of Vector Store using Astra DB with search capabilities",
                                        "display_name": "Astra DB",
                                        "documentation": "https://python.langchain.com/docs/integrations/vectorstores/astradb",
                                        "edited": False,
                                        "field_order": [
                                            "collection_name",
                                            "token",
                                            "api_endpoint",
                                            "search_input",
                                            "ingest_data",
                                            "namespace",
                                            "metric",
                                            "batch_size",
                                            "bulk_insert_batch_concurrency",
                                            "bulk_insert_overwrite_concurrency",
                                            "bulk_delete_concurrency",
                                            "setup_mode",
                                            "pre_delete_collection",
                                            "metadata_indexing_include",
                                            "embedding",
                                            "metadata_indexing_exclude",
                                            "collection_indexing_policy",
                                            "number_of_results",
                                            "search_type",
                                            "search_score_threshold",
                                            "search_filter"
                                        ],
                                        "frozen": False,
                                        "icon": "AstraDB",
                                        "output_types": [],
                                        "outputs": [
                                            {
                                                "cache": True,
                                                "display_name": "Retriever",
                                                "method": "build_base_retriever",
                                                "name": "base_retriever",
                                                "selected": "Retriever",
                                                "types": [
                                                    "Retriever"
                                                ],
                                                "value": "__UNDEFINED__"
                                            },
                                            {
                                                "cache": True,
                                                "display_name": "Search Results",
                                                "method": "search_documents",
                                                "name": "search_results",
                                                "selected": "Data",
                                                "types": [
                                                    "Data"
                                                ],
                                                "value": "__UNDEFINED__"
                                            },
                                            {
                                                "cache": True,
                                                "display_name": "Vector Store",
                                                "method": "cast_vector_store",
                                                "name": "vector_store",
                                                "selected": "VectorStore",
                                                "types": [
                                                    "VectorStore"
                                                ],
                                                "value": "__UNDEFINED__"
                                            }
                                        ],
                                        "pinned": False,
                                        "template": {
                                            "_type": "Component",
                                            "api_endpoint": {
                                                "advanced": False,
                                                "display_name": "API Endpoint",
                                                "dynamic": False,
                                                "info": "API endpoint URL for the Astra DB service.",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "load_from_db": True,
                                                "name": "api_endpoint",
                                                "password": True,
                                                "placeholder": "",
                                                "required": True,
                                                "show": True,
                                                "title_case": False,
                                                "type": "str",
                                                "value": "ASTRA_DB_API_ENDPOINT"
                                            },
                                            "batch_size": {
                                                "advanced": True,
                                                "display_name": "Batch Size",
                                                "dynamic": False,
                                                "info": "Optional number of data to process in a single batch.",
                                                "list": False,
                                                "name": "batch_size",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "int",
                                                "value": ""
                                            },
                                            "bulk_delete_concurrency": {
                                                "advanced": True,
                                                "display_name": "Bulk Delete Concurrency",
                                                "dynamic": False,
                                                "info": "Optional concurrency level for bulk delete operations.",
                                                "list": False,
                                                "name": "bulk_delete_concurrency",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "int",
                                                "value": ""
                                            },
                                            "bulk_insert_batch_concurrency": {
                                                "advanced": True,
                                                "display_name": "Bulk Insert Batch Concurrency",
                                                "dynamic": False,
                                                "info": "Optional concurrency level for bulk insert operations.",
                                                "list": False,
                                                "name": "bulk_insert_batch_concurrency",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "int",
                                                "value": ""
                                            },
                                            "bulk_insert_overwrite_concurrency": {
                                                "advanced": True,
                                                "display_name": "Bulk Insert Overwrite Concurrency",
                                                "dynamic": False,
                                                "info": "Optional concurrency level for bulk insert operations that overwrite existing data.",
                                                "list": False,
                                                "name": "bulk_insert_overwrite_concurrency",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "int",
                                                "value": ""
                                            },
                                            "code": {
                                                "advanced": True,
                                                "dynamic": True,
                                                "fileTypes": [],
                                                "file_path": "",
                                                "info": "",
                                                "list": False,
                                                "load_from_db": False,
                                                "multiline": True,
                                                "name": "code",
                                                "password": False,
                                                "placeholder": "",
                                                "required": True,
                                                "show": True,
                                                "title_case": False,
                                                "type": "code",
                                                "value": "from loguru import logger\n\nfrom langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store\nfrom langflow.helpers import docs_to_data\nfrom langflow.inputs import DictInput, FloatInput\nfrom langflow.io import (\n    BoolInput,\n    DataInput,\n    DropdownInput,\n    HandleInput,\n    IntInput,\n    MultilineInput,\n    SecretStrInput,\n    StrInput,\n)\nfrom langflow.schema import Data\n\n\nclass AstraVectorStoreComponent(LCVectorStoreComponent):\n    display_name: str = \"Astra DB\"\n    description: str = \"Implementation of Vector Store using Astra DB with search capabilities\"\n    documentation: str = \"https://python.langchain.com/docs/integrations/vectorstores/astradb\"\n    name = \"AstraDB\"\n    icon: str = \"AstraDB\"\n\n    inputs = [\n        StrInput(\n            name=\"collection_name\",\n            display_name=\"Collection Name\",\n            info=\"The name of the collection within Astra DB where the vectors will be stored.\",\n            required=True,\n        ),\n        SecretStrInput(\n            name=\"token\",\n            display_name=\"Astra DB Application Token\",\n            info=\"Authentication token for accessing Astra DB.\",\n            value=\"ASTRA_DB_APPLICATION_TOKEN\",\n            required=True,\n        ),\n        SecretStrInput(\n            name=\"api_endpoint\",\n            display_name=\"API Endpoint\",\n            info=\"API endpoint URL for the Astra DB service.\",\n            value=\"ASTRA_DB_API_ENDPOINT\",\n            required=True,\n        ),\n        MultilineInput(\n            name=\"search_input\",\n            display_name=\"Search Input\",\n        ),\n        DataInput(\n            name=\"ingest_data\",\n            display_name=\"Ingest Data\",\n            is_list=True,\n        ),\n        StrInput(\n            name=\"namespace\",\n            display_name=\"Namespace\",\n            info=\"Optional namespace within Astra DB to use for the collection.\",\n            advanced=True,\n        ),\n        DropdownInput(\n            name=\"metric\",\n            display_name=\"Metric\",\n            info=\"Optional distance metric for vector comparisons in the vector store.\",\n            options=[\"cosine\", \"dot_product\", \"euclidean\"],\n            advanced=True,\n        ),\n        IntInput(\n            name=\"batch_size\",\n            display_name=\"Batch Size\",\n            info=\"Optional number of data to process in a single batch.\",\n            advanced=True,\n        ),\n        IntInput(\n            name=\"bulk_insert_batch_concurrency\",\n            display_name=\"Bulk Insert Batch Concurrency\",\n            info=\"Optional concurrency level for bulk insert operations.\",\n            advanced=True,\n        ),\n        IntInput(\n            name=\"bulk_insert_overwrite_concurrency\",\n            display_name=\"Bulk Insert Overwrite Concurrency\",\n            info=\"Optional concurrency level for bulk insert operations that overwrite existing data.\",\n            advanced=True,\n        ),\n        IntInput(\n            name=\"bulk_delete_concurrency\",\n            display_name=\"Bulk Delete Concurrency\",\n            info=\"Optional concurrency level for bulk delete operations.\",\n            advanced=True,\n        ),\n        DropdownInput(\n            name=\"setup_mode\",\n            display_name=\"Setup Mode\",\n            info=\"Configuration mode for setting up the vector store, with options like 'Sync', 'Async', or 'Off'.\",\n            options=[\"Sync\", \"Async\", \"Off\"],\n            advanced=True,\n            value=\"Sync\",\n        ),\n        BoolInput(\n            name=\"pre_delete_collection\",\n            display_name=\"Pre Delete Collection\",\n            info=\"Boolean flag to determine whether to delete the collection before creating a new one.\",\n            advanced=True,\n        ),\n        StrInput(\n            name=\"metadata_indexing_include\",\n            display_name=\"Metadata Indexing Include\",\n            info=\"Optional list of metadata fields to include in the indexing.\",\n            advanced=True,\n        ),\n        HandleInput(\n            name=\"embedding\",\n            display_name=\"Embedding or Astra Vectorize\",\n            input_types=[\"Embeddings\", \"dict\"],\n            info=\"Allows either an embedding model or an Astra Vectorize configuration.\",  # TODO: This should be optional, but need to refactor langchain-astradb first.\n        ),\n        StrInput(\n            name=\"metadata_indexing_exclude\",\n            display_name=\"Metadata Indexing Exclude\",\n            info=\"Optional list of metadata fields to exclude from the indexing.\",\n            advanced=True,\n        ),\n        StrInput(\n            name=\"collection_indexing_policy\",\n            display_name=\"Collection Indexing Policy\",\n            info=\"Optional dictionary defining the indexing policy for the collection.\",\n            advanced=True,\n        ),\n        IntInput(\n            name=\"number_of_results\",\n            display_name=\"Number of Results\",\n            info=\"Number of results to return.\",\n            advanced=True,\n            value=4,\n        ),\n        DropdownInput(\n            name=\"search_type\",\n            display_name=\"Search Type\",\n            info=\"Search type to use\",\n            options=[\"Similarity\", \"Similarity with score threshold\", \"MMR (Max Marginal Relevance)\"],\n            value=\"Similarity\",\n            advanced=True,\n        ),\n        FloatInput(\n            name=\"search_score_threshold\",\n            display_name=\"Search Score Threshold\",\n            info=\"Minimum similarity score threshold for search results. (when using 'Similarity with score threshold')\",\n            value=0,\n            advanced=True,\n        ),\n        DictInput(\n            name=\"search_filter\",\n            display_name=\"Search Metadata Filter\",\n            info=\"Optional dictionary of filters to apply to the search query.\",\n            advanced=True,\n            is_list=True,\n        ),\n    ]\n\n    @check_cached_vector_store\n    def build_vector_store(self):\n        try:\n            from langchain_astradb import AstraDBVectorStore\n            from langchain_astradb.utils.astradb import SetupMode\n        except ImportError:\n            raise ImportError(\n                \"Could not import langchain Astra DB integration package. \"\n                \"Please install it with `pip install langchain-astradb`.\"\n            )\n\n        try:\n            if not self.setup_mode:\n                self.setup_mode = self._inputs[\"setup_mode\"].options[0]\n\n            setup_mode_value = SetupMode[self.setup_mode.upper()]\n        except KeyError:\n            raise ValueError(f\"Invalid setup mode: {self.setup_mode}\")\n\n        if not isinstance(self.embedding, dict):\n            embedding_dict = {\"embedding\": self.embedding}\n        else:\n            from astrapy.info import CollectionVectorServiceOptions\n\n            dict_options = self.embedding.get(\"collection_vector_service_options\", {})\n            dict_options[\"authentication\"] = {\n                k: v for k, v in dict_options.get(\"authentication\", {}).items() if k and v\n            }\n            dict_options[\"parameters\"] = {k: v for k, v in dict_options.get(\"parameters\", {}).items() if k and v}\n            embedding_dict = {\n                \"collection_vector_service_options\": CollectionVectorServiceOptions.from_dict(dict_options)\n            }\n            collection_embedding_api_key = self.embedding.get(\"collection_embedding_api_key\")\n            if collection_embedding_api_key:\n                embedding_dict[\"collection_embedding_api_key\"] = collection_embedding_api_key\n\n        vector_store_kwargs = {\n            **embedding_dict,\n            \"collection_name\": self.collection_name,\n            \"token\": self.token,\n            \"api_endpoint\": self.api_endpoint,\n            \"namespace\": self.namespace or None,\n            \"metric\": self.metric or None,\n            \"batch_size\": self.batch_size or None,\n            \"bulk_insert_batch_concurrency\": self.bulk_insert_batch_concurrency or None,\n            \"bulk_insert_overwrite_concurrency\": self.bulk_insert_overwrite_concurrency or None,\n            \"bulk_delete_concurrency\": self.bulk_delete_concurrency or None,\n            \"setup_mode\": setup_mode_value,\n            \"pre_delete_collection\": self.pre_delete_collection or False,\n        }\n\n        if self.metadata_indexing_include:\n            vector_store_kwargs[\"metadata_indexing_include\"] = self.metadata_indexing_include\n        elif self.metadata_indexing_exclude:\n            vector_store_kwargs[\"metadata_indexing_exclude\"] = self.metadata_indexing_exclude\n        elif self.collection_indexing_policy:\n            vector_store_kwargs[\"collection_indexing_policy\"] = self.collection_indexing_policy\n\n        try:\n            vector_store = AstraDBVectorStore(**vector_store_kwargs)\n        except Exception as e:\n            raise ValueError(f\"Error initializing AstraDBVectorStore: {str(e)}\") from e\n\n        self._add_documents_to_vector_store(vector_store)\n        return vector_store\n\n    def _add_documents_to_vector_store(self, vector_store):\n        documents = []\n        for _input in self.ingest_data or []:\n            if isinstance(_input, Data):\n                documents.append(_input.to_lc_document())\n            else:\n                raise ValueError(\"Vector Store Inputs must be Data objects.\")\n\n        if documents:\n            logger.debug(f\"Adding {len(documents)} documents to the Vector Store.\")\n            try:\n                vector_store.add_documents(documents)\n            except Exception as e:\n                raise ValueError(f\"Error adding documents to AstraDBVectorStore: {str(e)}\") from e\n        else:\n            logger.debug(\"No documents to add to the Vector Store.\")\n\n    def _map_search_type(self):\n        if self.search_type == \"Similarity with score threshold\":\n            return \"similarity_score_threshold\"\n        elif self.search_type == \"MMR (Max Marginal Relevance)\":\n            return \"mmr\"\n        else:\n            return \"similarity\"\n\n    def _build_search_args(self):\n        args = {\n            \"k\": self.number_of_results,\n            \"score_threshold\": self.search_score_threshold,\n        }\n\n        if self.search_filter:\n            clean_filter = {k: v for k, v in self.search_filter.items() if k and v}\n            if len(clean_filter) > 0:\n                args[\"filter\"] = clean_filter\n        return args\n\n    def search_documents(self) -> list[Data]:\n        vector_store = self.build_vector_store()\n\n        logger.debug(f\"Search input: {self.search_input}\")\n        logger.debug(f\"Search type: {self.search_type}\")\n        logger.debug(f\"Number of results: {self.number_of_results}\")\n\n        if self.search_input and isinstance(self.search_input, str) and self.search_input.strip():\n            try:\n                search_type = self._map_search_type()\n                search_args = self._build_search_args()\n\n                docs = vector_store.search(query=self.search_input, search_type=search_type, **search_args)\n            except Exception as e:\n                raise ValueError(f\"Error performing search in AstraDBVectorStore: {str(e)}\") from e\n\n            logger.debug(f\"Retrieved documents: {len(docs)}\")\n\n            data = docs_to_data(docs)\n            logger.debug(f\"Converted documents to data: {len(data)}\")\n            self.status = data\n            return data\n        else:\n            logger.debug(\"No search input provided. Skipping search.\")\n            return []\n\n    def get_retriever_kwargs(self):\n        search_args = self._build_search_args()\n        return {\n            \"search_type\": self._map_search_type(),\n            \"search_kwargs\": search_args,\n        }\n"
                                            },
                                            "collection_indexing_policy": {
                                                "advanced": True,
                                                "display_name": "Collection Indexing Policy",
                                                "dynamic": False,
                                                "info": "Optional dictionary defining the indexing policy for the collection.",
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "collection_indexing_policy",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "collection_name": {
                                                "advanced": False,
                                                "display_name": "Collection Name",
                                                "dynamic": False,
                                                "info": "The name of the collection within Astra DB where the vectors will be stored.",
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "collection_name",
                                                "placeholder": "",
                                                "required": True,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": "langflow"
                                            },
                                            "embedding": {
                                                "advanced": False,
                                                "display_name": "Embedding or Astra Vectorize",
                                                "dynamic": False,
                                                "info": "Allows either an embedding model or an Astra Vectorize configuration.",
                                                "input_types": [
                                                    "Embeddings",
                                                    "dict"
                                                ],
                                                "list": False,
                                                "name": "embedding",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "other",
                                                "value": ""
                                            },
                                            "ingest_data": {
                                                "advanced": False,
                                                "display_name": "Ingest Data",
                                                "dynamic": False,
                                                "info": "",
                                                "input_types": [
                                                    "Data"
                                                ],
                                                "list": True,
                                                "name": "ingest_data",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "other",
                                                "value": ""
                                            },
                                            "metadata_indexing_exclude": {
                                                "advanced": True,
                                                "display_name": "Metadata Indexing Exclude",
                                                "dynamic": False,
                                                "info": "Optional list of metadata fields to exclude from the indexing.",
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "metadata_indexing_exclude",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "metadata_indexing_include": {
                                                "advanced": True,
                                                "display_name": "Metadata Indexing Include",
                                                "dynamic": False,
                                                "info": "Optional list of metadata fields to include in the indexing.",
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "metadata_indexing_include",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "metric": {
                                                "advanced": True,
                                                "display_name": "Metric",
                                                "dynamic": False,
                                                "info": "Optional distance metric for vector comparisons in the vector store.",
                                                "name": "metric",
                                                "options": [
                                                    "cosine",
                                                    "dot_product",
                                                    "euclidean"
                                                ],
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "namespace": {
                                                "advanced": True,
                                                "display_name": "Namespace",
                                                "dynamic": False,
                                                "info": "Optional namespace within Astra DB to use for the collection.",
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "namespace",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "number_of_results": {
                                                "advanced": True,
                                                "display_name": "Number of Results",
                                                "dynamic": False,
                                                "info": "Number of results to return.",
                                                "list": False,
                                                "name": "number_of_results",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "int",
                                                "value": 4
                                            },
                                            "pre_delete_collection": {
                                                "advanced": True,
                                                "display_name": "Pre Delete Collection",
                                                "dynamic": False,
                                                "info": "Boolean flag to determine whether to delete the collection before creating a new one.",
                                                "list": False,
                                                "name": "pre_delete_collection",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "bool",
                                                "value": False
                                            },
                                            "search_filter": {
                                                "advanced": True,
                                                "display_name": "Search Metadata Filter",
                                                "dynamic": False,
                                                "info": "Optional dictionary of filters to apply to the search query.",
                                                "list": True,
                                                "name": "search_filter",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "type": "dict",
                                                "value": {}
                                            },
                                            "search_input": {
                                                "advanced": False,
                                                "display_name": "Search Input",
                                                "dynamic": False,
                                                "info": "",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "list": False,
                                                "load_from_db": False,
                                                "multiline": True,
                                                "name": "search_input",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "search_score_threshold": {
                                                "advanced": True,
                                                "display_name": "Search Score Threshold",
                                                "dynamic": False,
                                                "info": "Minimum similarity score threshold for search results. (when using 'Similarity with score threshold')",
                                                "list": False,
                                                "name": "search_score_threshold",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "float",
                                                "value": 0
                                            },
                                            "search_type": {
                                                "advanced": True,
                                                "display_name": "Search Type",
                                                "dynamic": False,
                                                "info": "Search type to use",
                                                "name": "search_type",
                                                "options": [
                                                    "Similarity",
                                                    "Similarity with score threshold",
                                                    "MMR (Max Marginal Relevance)"
                                                ],
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": "Similarity"
                                            },
                                            "setup_mode": {
                                                "advanced": True,
                                                "display_name": "Setup Mode",
                                                "dynamic": False,
                                                "info": "Configuration mode for setting up the vector store, with options like 'Sync', 'Async', or 'Off'.",
                                                "name": "setup_mode",
                                                "options": [
                                                    "Sync",
                                                    "Async",
                                                    "Off"
                                                ],
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": "Sync"
                                            },
                                            "token": {
                                                "advanced": False,
                                                "display_name": "Astra DB Application Token",
                                                "dynamic": False,
                                                "info": "Authentication token for accessing Astra DB.",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "load_from_db": True,
                                                "name": "token",
                                                "password": True,
                                                "placeholder": "",
                                                "required": True,
                                                "show": True,
                                                "title_case": False,
                                                "type": "str",
                                                "value": "ASTRA_DB_APPLICATION_TOKEN"
                                            }
                                        }
                                    },
                                    "type": "AstraVectorStoreComponent"
                                },
                                "dragging": False,
                                "height": 774,
                                "id": "AstraVectorStoreComponent-XE3MH",
                                "position": {
                                    "x": 1246.0381406498648,
                                    "y": 333.25157075413966
                                },
                                "positionAbsolute": {
                                    "x": 1246.0381406498648,
                                    "y": 333.25157075413966
                                },
                                "selected": True,
                                "type": "genericNode",
                                "width": 384
                            },
                            {
                                "data": {
                                    "description": "Convert Data into plain text following a specified template.",
                                    "display_name": "Parse Data",
                                    "id": "ParseData-ILuxa",
                                    "node": {
                                        "base_classes": [
                                            "Message"
                                        ],
                                        "beta": False,
                                        "conditional_paths": [],
                                        "custom_fields": {},
                                        "description": "Convert Data into plain text following a specified template.",
                                        "display_name": "Parse Data",
                                        "documentation": "",
                                        "edited": False,
                                        "field_order": [
                                            "data",
                                            "template",
                                            "sep"
                                        ],
                                        "frozen": False,
                                        "icon": "braces",
                                        "output_types": [],
                                        "outputs": [
                                            {
                                                "cache": True,
                                                "display_name": "Text",
                                                "method": "parse_data",
                                                "name": "text",
                                                "selected": "Message",
                                                "types": [
                                                    "Message"
                                                ],
                                                "value": "__UNDEFINED__"
                                            }
                                        ],
                                        "pinned": False,
                                        "template": {
                                            "_type": "Component",
                                            "code": {
                                                "advanced": True,
                                                "dynamic": True,
                                                "fileTypes": [],
                                                "file_path": "",
                                                "info": "",
                                                "list": False,
                                                "load_from_db": False,
                                                "multiline": True,
                                                "name": "code",
                                                "password": False,
                                                "placeholder": "",
                                                "required": True,
                                                "show": True,
                                                "title_case": False,
                                                "type": "code",
                                                "value": "from langflow.custom import Component\nfrom langflow.helpers.data import data_to_text\nfrom langflow.io import DataInput, MultilineInput, Output, StrInput\nfrom langflow.schema.message import Message\n\n\nclass ParseDataComponent(Component):\n    display_name = \"Parse Data\"\n    description = \"Convert Data into plain text following a specified template.\"\n    icon = \"braces\"\n    name = \"ParseData\"\n\n    inputs = [\n        DataInput(name=\"data\", display_name=\"Data\", info=\"The data to convert to text.\"),\n        MultilineInput(\n            name=\"template\",\n            display_name=\"Template\",\n            info=\"The template to use for formatting the data. It can contain the keys {text}, {data} or any other key in the Data.\",\n            value=\"{text}\",\n        ),\n        StrInput(name=\"sep\", display_name=\"Separator\", advanced=True, value=\"\\n\"),\n    ]\n\n    outputs = [\n        Output(display_name=\"Text\", name=\"text\", method=\"parse_data\"),\n    ]\n\n    def parse_data(self) -> Message:\n        data = self.data if isinstance(self.data, list) else [self.data]\n        template = self.template\n\n        result_string = data_to_text(template, data, sep=self.sep)\n        self.status = result_string\n        return Message(text=result_string)\n"
                                            },
                                            "data": {
                                                "advanced": False,
                                                "display_name": "Data",
                                                "dynamic": False,
                                                "info": "The data to convert to text.",
                                                "input_types": [
                                                    "Data"
                                                ],
                                                "list": False,
                                                "name": "data",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "other",
                                                "value": ""
                                            },
                                            "sep": {
                                                "advanced": True,
                                                "display_name": "Separator",
                                                "dynamic": False,
                                                "info": "",
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "sep",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": "\n"
                                            },
                                            "template": {
                                                "advanced": False,
                                                "display_name": "Template",
                                                "dynamic": False,
                                                "info": "The template to use for formatting the data. It can contain the keys {text}, {data} or any other key in the Data.",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "list": False,
                                                "load_from_db": False,
                                                "multiline": True,
                                                "name": "template",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": "{text}"
                                            }
                                        }
                                    },
                                    "type": "ParseData"
                                },
                                "dragging": False,
                                "height": 378,
                                "id": "ParseData-ILuxa",
                                "position": {
                                    "x": 1854.1518317915907,
                                    "y": 459.3386924128532
                                },
                                "positionAbsolute": {
                                    "x": 1854.1518317915907,
                                    "y": 459.3386924128532
                                },
                                "selected": False,
                                "type": "genericNode",
                                "width": 384
                            },
                            {
                                "data": {
                                    "description": "Create a prompt template with dynamic variables.",
                                    "display_name": "Prompt",
                                    "id": "Prompt-Tfriy",
                                    "node": {
                                        "base_classes": [
                                            "Message"
                                        ],
                                        "beta": False,
                                        "conditional_paths": [],
                                        "custom_fields": {
                                            "template": [
                                                "context",
                                                "question"
                                            ]
                                        },
                                        "description": "Create a prompt template with dynamic variables.",
                                        "display_name": "Prompt",
                                        "documentation": "",
                                        "edited": False,
                                        "field_order": [
                                            "template"
                                        ],
                                        "frozen": False,
                                        "icon": "prompts",
                                        "output_types": [],
                                        "outputs": [
                                            {
                                                "cache": True,
                                                "display_name": "Prompt Message",
                                                "method": "build_prompt",
                                                "name": "prompt",
                                                "selected": "Message",
                                                "types": [
                                                    "Message"
                                                ],
                                                "value": "__UNDEFINED__"
                                            }
                                        ],
                                        "pinned": False,
                                        "template": {
                                            "_type": "Component",
                                            "code": {
                                                "advanced": True,
                                                "dynamic": True,
                                                "fileTypes": [],
                                                "file_path": "",
                                                "info": "",
                                                "list": False,
                                                "load_from_db": False,
                                                "multiline": True,
                                                "name": "code",
                                                "password": False,
                                                "placeholder": "",
                                                "required": True,
                                                "show": True,
                                                "title_case": False,
                                                "type": "code",
                                                "value": "from langflow.base.prompts.api_utils import process_prompt_template\nfrom langflow.custom import Component\nfrom langflow.inputs.inputs import DefaultPromptField\nfrom langflow.io import Output, PromptInput\nfrom langflow.schema.message import Message\nfrom langflow.template.utils import update_template_values\n\n\nclass PromptComponent(Component):\n    display_name: str = \"Prompt\"\n    description: str = \"Create a prompt template with dynamic variables.\"\n    icon = \"prompts\"\n    trace_type = \"prompt\"\n    name = \"Prompt\"\n\n    inputs = [\n        PromptInput(name=\"template\", display_name=\"Template\"),\n    ]\n\n    outputs = [\n        Output(display_name=\"Prompt Message\", name=\"prompt\", method=\"build_prompt\"),\n    ]\n\n    async def build_prompt(\n        self,\n    ) -> Message:\n        prompt = await Message.from_template_and_variables(**self._attributes)\n        self.status = prompt.text\n        return prompt\n\n    def _update_template(self, frontend_node: dict):\n        prompt_template = frontend_node[\"template\"][\"template\"][\"value\"]\n        custom_fields = frontend_node[\"custom_fields\"]\n        frontend_node_template = frontend_node[\"template\"]\n        _ = process_prompt_template(\n            template=prompt_template,\n            name=\"template\",\n            custom_fields=custom_fields,\n            frontend_node_template=frontend_node_template,\n        )\n        return frontend_node\n\n    def post_code_processing(self, new_frontend_node: dict, current_frontend_node: dict):\n        \"\"\"\n        This function is called after the code validation is done.\n        \"\"\"\n        frontend_node = super().post_code_processing(new_frontend_node, current_frontend_node)\n        template = frontend_node[\"template\"][\"template\"][\"value\"]\n        # Kept it duplicated for backwards compatibility\n        _ = process_prompt_template(\n            template=template,\n            name=\"template\",\n            custom_fields=frontend_node[\"custom_fields\"],\n            frontend_node_template=frontend_node[\"template\"],\n        )\n        # Now that template is updated, we need to grab any values that were set in the current_frontend_node\n        # and update the frontend_node with those values\n        update_template_values(new_template=frontend_node, previous_template=current_frontend_node[\"template\"])\n        return frontend_node\n\n    def _get_fallback_input(self, **kwargs):\n        return DefaultPromptField(**kwargs)\n"
                                            },
                                            "context": {
                                                "advanced": False,
                                                "display_name": "context",
                                                "dynamic": False,
                                                "field_type": "str",
                                                "fileTypes": [],
                                                "file_path": "",
                                                "info": "",
                                                "input_types": [
                                                    "Message",
                                                    "Text"
                                                ],
                                                "list": False,
                                                "load_from_db": False,
                                                "multiline": True,
                                                "name": "context",
                                                "password": False,
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "question": {
                                                "advanced": False,
                                                "display_name": "question",
                                                "dynamic": False,
                                                "field_type": "str",
                                                "fileTypes": [],
                                                "file_path": "",
                                                "info": "",
                                                "input_types": [
                                                    "Message",
                                                    "Text"
                                                ],
                                                "list": False,
                                                "load_from_db": False,
                                                "multiline": True,
                                                "name": "question",
                                                "password": False,
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "template": {
                                                "advanced": False,
                                                "display_name": "Template",
                                                "dynamic": False,
                                                "info": "",
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "template",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "type": "prompt",
                                                "value": "{context}\n\n---\n\nGiven the context above, answer the question as best as possible.\n\nQuestion: {question}\n\nAnswer: "
                                            }
                                        }
                                    },
                                    "type": "Prompt"
                                },
                                "dragging": False,
                                "height": 502,
                                "id": "Prompt-Tfriy",
                                "position": {
                                    "x": 2486.0988668404975,
                                    "y": 496.5120474157301
                                },
                                "positionAbsolute": {
                                    "x": 2486.0988668404975,
                                    "y": 496.5120474157301
                                },
                                "selected": False,
                                "type": "genericNode",
                                "width": 384
                            },
                            {
                                "data": {
                                    "description": "Display a chat message in the Playground.",
                                    "display_name": "Chat Output",
                                    "id": "ChatOutput-Mh7FA",
                                    "node": {
                                        "base_classes": [
                                            "Message"
                                        ],
                                        "beta": False,
                                        "conditional_paths": [],
                                        "custom_fields": {},
                                        "description": "Display a chat message in the Playground.",
                                        "display_name": "Chat Output",
                                        "documentation": "",
                                        "edited": False,
                                        "field_order": [
                                            "input_value",
                                            "should_store_message",
                                            "sender",
                                            "sender_name",
                                            "session_id",
                                            "data_template"
                                        ],
                                        "frozen": False,
                                        "icon": "ChatOutput",
                                        "output_types": [],
                                        "outputs": [
                                            {
                                                "cache": True,
                                                "display_name": "Message",
                                                "method": "message_response",
                                                "name": "message",
                                                "selected": "Message",
                                                "types": [
                                                    "Message"
                                                ],
                                                "value": "__UNDEFINED__"
                                            }
                                        ],
                                        "pinned": False,
                                        "template": {
                                            "_type": "Component",
                                            "code": {
                                                "advanced": True,
                                                "dynamic": True,
                                                "fileTypes": [],
                                                "file_path": "",
                                                "info": "",
                                                "list": False,
                                                "load_from_db": False,
                                                "multiline": True,
                                                "name": "code",
                                                "password": False,
                                                "placeholder": "",
                                                "required": True,
                                                "show": True,
                                                "title_case": False,
                                                "type": "code",
                                                "value": "from langflow.base.io.chat import ChatComponent\nfrom langflow.inputs import BoolInput\nfrom langflow.io import DropdownInput, MessageTextInput, Output\nfrom langflow.memory import store_message\nfrom langflow.schema.message import Message\nfrom langflow.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_NAME_AI, MESSAGE_SENDER_USER\n\n\nclass ChatOutput(ChatComponent):\n    display_name = \"Chat Output\"\n    description = \"Display a chat message in the Playground.\"\n    icon = \"ChatOutput\"\n    name = \"ChatOutput\"\n\n    inputs = [\n        MessageTextInput(\n            name=\"input_value\",\n            display_name=\"Text\",\n            info=\"Message to be passed as output.\",\n        ),\n        BoolInput(\n            name=\"should_store_message\",\n            display_name=\"Store Messages\",\n            info=\"Store the message in the history.\",\n            value=True,\n            advanced=True,\n        ),\n        DropdownInput(\n            name=\"sender\",\n            display_name=\"Sender Type\",\n            options=[MESSAGE_SENDER_AI, MESSAGE_SENDER_USER],\n            value=MESSAGE_SENDER_AI,\n            advanced=True,\n            info=\"Type of sender.\",\n        ),\n        MessageTextInput(\n            name=\"sender_name\",\n            display_name=\"Sender Name\",\n            info=\"Name of the sender.\",\n            value=MESSAGE_SENDER_NAME_AI,\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"session_id\",\n            display_name=\"Session ID\",\n            info=\"The session ID of the chat. If empty, the current session ID parameter will be used.\",\n            advanced=True,\n        ),\n        MessageTextInput(\n            name=\"data_template\",\n            display_name=\"Data Template\",\n            value=\"{text}\",\n            advanced=True,\n            info=\"Template to convert Data to Text. If left empty, it will be dynamically set to the Data's text key.\",\n        ),\n    ]\n    outputs = [\n        Output(display_name=\"Message\", name=\"message\", method=\"message_response\"),\n    ]\n\n    def message_response(self) -> Message:\n        message = Message(\n            text=self.input_value,\n            sender=self.sender,\n            sender_name=self.sender_name,\n            session_id=self.session_id,\n        )\n        if (\n            self.session_id\n            and isinstance(message, Message)\n            and isinstance(message.text, str)\n            and self.should_store_message\n        ):\n            store_message(\n                message,\n                flow_id=self.graph.flow_id,\n            )\n            self.message.value = message\n\n        self.status = message\n        return message\n"
                                            },
                                            "data_template": {
                                                "advanced": True,
                                                "display_name": "Data Template",
                                                "dynamic": False,
                                                "info": "Template to convert Data to Text. If left empty, it will be dynamically set to the Data's text key.",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "data_template",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": "{text}"
                                            },
                                            "input_value": {
                                                "advanced": False,
                                                "display_name": "Text",
                                                "dynamic": False,
                                                "info": "Message to be passed as output.",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "input_value",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "sender": {
                                                "advanced": True,
                                                "display_name": "Sender Type",
                                                "dynamic": False,
                                                "info": "Type of sender.",
                                                "name": "sender",
                                                "options": [
                                                    "Machine",
                                                    "User"
                                                ],
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": "Machine"
                                            },
                                            "sender_name": {
                                                "advanced": True,
                                                "display_name": "Sender Name",
                                                "dynamic": False,
                                                "info": "Name of the sender.",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "sender_name",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": "AI"
                                            },
                                            "session_id": {
                                                "advanced": True,
                                                "display_name": "Session ID",
                                                "dynamic": False,
                                                "info": "The session ID of the chat. If empty, the current session ID parameter will be used.",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "session_id",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "should_store_message": {
                                                "advanced": True,
                                                "display_name": "Store Messages",
                                                "dynamic": False,
                                                "info": "Store the message in the history.",
                                                "list": False,
                                                "name": "should_store_message",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "bool",
                                                "value": True
                                            }
                                        }
                                    },
                                    "type": "ChatOutput"
                                },
                                "dragging": False,
                                "height": 302,
                                "id": "ChatOutput-Mh7FA",
                                "position": {
                                    "x": 3769.242086248817,
                                    "y": 585.3403837062634
                                },
                                "positionAbsolute": {
                                    "x": 3769.242086248817,
                                    "y": 585.3403837062634
                                },
                                "selected": False,
                                "type": "genericNode",
                                "width": 384
                            },
                            {
                                "data": {
                                    "description": "Split text into chunks based on specified criteria.",
                                    "display_name": "Split Text",
                                    "id": "SplitText-rAbUh",
                                    "node": {
                                        "base_classes": [
                                            "Data"
                                        ],
                                        "beta": False,
                                        "conditional_paths": [],
                                        "custom_fields": {},
                                        "description": "Split text into chunks based on specified criteria.",
                                        "display_name": "Split Text",
                                        "documentation": "",
                                        "edited": False,
                                        "field_order": [
                                            "data_inputs",
                                            "chunk_overlap",
                                            "chunk_size",
                                            "separator"
                                        ],
                                        "frozen": False,
                                        "icon": "scissors-line-dashed",
                                        "output_types": [],
                                        "outputs": [
                                            {
                                                "cache": True,
                                                "display_name": "Chunks",
                                                "method": "split_text",
                                                "name": "chunks",
                                                "selected": "Data",
                                                "types": [
                                                    "Data"
                                                ],
                                                "value": "__UNDEFINED__"
                                            }
                                        ],
                                        "pinned": False,
                                        "template": {
                                            "_type": "Component",
                                            "chunk_overlap": {
                                                "advanced": False,
                                                "display_name": "Chunk Overlap",
                                                "dynamic": False,
                                                "info": "Number of characters to overlap between chunks.",
                                                "list": False,
                                                "name": "chunk_overlap",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "int",
                                                "value": 200
                                            },
                                            "chunk_size": {
                                                "advanced": False,
                                                "display_name": "Chunk Size",
                                                "dynamic": False,
                                                "info": "The maximum number of characters in each chunk.",
                                                "list": False,
                                                "name": "chunk_size",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "int",
                                                "value": 1000
                                            },
                                            "code": {
                                                "advanced": True,
                                                "dynamic": True,
                                                "fileTypes": [],
                                                "file_path": "",
                                                "info": "",
                                                "list": False,
                                                "load_from_db": False,
                                                "multiline": True,
                                                "name": "code",
                                                "password": False,
                                                "placeholder": "",
                                                "required": True,
                                                "show": True,
                                                "title_case": False,
                                                "type": "code",
                                                "value": "from typing import List\n\nfrom langchain_text_splitters import CharacterTextSplitter\n\nfrom langflow.custom import Component\nfrom langflow.io import HandleInput, IntInput, MessageTextInput, Output\nfrom langflow.schema import Data\nfrom langflow.utils.util import unescape_string\n\n\nclass SplitTextComponent(Component):\n    display_name: str = \"Split Text\"\n    description: str = \"Split text into chunks based on specified criteria.\"\n    icon = \"scissors-line-dashed\"\n    name = \"SplitText\"\n\n    inputs = [\n        HandleInput(\n            name=\"data_inputs\",\n            display_name=\"Data Inputs\",\n            info=\"The data to split.\",\n            input_types=[\"Data\"],\n            is_list=True,\n        ),\n        IntInput(\n            name=\"chunk_overlap\",\n            display_name=\"Chunk Overlap\",\n            info=\"Number of characters to overlap between chunks.\",\n            value=200,\n        ),\n        IntInput(\n            name=\"chunk_size\",\n            display_name=\"Chunk Size\",\n            info=\"The maximum number of characters in each chunk.\",\n            value=1000,\n        ),\n        MessageTextInput(\n            name=\"separator\",\n            display_name=\"Separator\",\n            info=\"The character to split on. Defaults to newline.\",\n            value=\"\\n\",\n        ),\n    ]\n\n    outputs = [\n        Output(display_name=\"Chunks\", name=\"chunks\", method=\"split_text\"),\n    ]\n\n    def _docs_to_data(self, docs):\n        data = []\n        for doc in docs:\n            data.append(Data(text=doc.page_content, data=doc.metadata))\n        return data\n\n    def split_text(self) -> List[Data]:\n        separator = unescape_string(self.separator)\n\n        documents = []\n        for _input in self.data_inputs:\n            if isinstance(_input, Data):\n                documents.append(_input.to_lc_document())\n\n        splitter = CharacterTextSplitter(\n            chunk_overlap=self.chunk_overlap,\n            chunk_size=self.chunk_size,\n            separator=separator,\n        )\n        docs = splitter.split_documents(documents)\n        data = self._docs_to_data(docs)\n        self.status = data\n        return data\n"
                                            },
                                            "data_inputs": {
                                                "advanced": False,
                                                "display_name": "Data Inputs",
                                                "dynamic": False,
                                                "info": "The data to split.",
                                                "input_types": [
                                                    "Data"
                                                ],
                                                "list": True,
                                                "name": "data_inputs",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "other",
                                                "value": ""
                                            },
                                            "separator": {
                                                "advanced": False,
                                                "display_name": "Separator",
                                                "dynamic": False,
                                                "info": "The character to split on. Defaults to newline.",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "separator",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": "\n"
                                            }
                                        }
                                    },
                                    "type": "SplitText"
                                },
                                "dragging": False,
                                "height": 550,
                                "id": "SplitText-rAbUh",
                                "position": {
                                    "x": 2044.2799160989089,
                                    "y": 1185.3130355818519
                                },
                                "positionAbsolute": {
                                    "x": 2044.2799160989089,
                                    "y": 1185.3130355818519
                                },
                                "selected": False,
                                "type": "genericNode",
                                "width": 384
                            },
                            {
                                "data": {
                                    "description": "A generic file loader.",
                                    "display_name": "File",
                                    "id": "File-TBV93",
                                    "node": {
                                        "base_classes": [
                                            "Data"
                                        ],
                                        "beta": False,
                                        "conditional_paths": [],
                                        "custom_fields": {},
                                        "description": "A generic file loader.",
                                        "display_name": "File",
                                        "documentation": "",
                                        "edited": False,
                                        "field_order": [
                                            "path",
                                            "silent_errors"
                                        ],
                                        "frozen": False,
                                        "icon": "file-text",
                                        "output_types": [],
                                        "outputs": [
                                            {
                                                "cache": True,
                                                "display_name": "Data",
                                                "method": "load_file",
                                                "name": "data",
                                                "selected": "Data",
                                                "types": [
                                                    "Data"
                                                ],
                                                "value": "__UNDEFINED__"
                                            }
                                        ],
                                        "pinned": False,
                                        "template": {
                                            "_type": "Component",
                                            "code": {
                                                "advanced": True,
                                                "dynamic": True,
                                                "fileTypes": [],
                                                "file_path": "",
                                                "info": "",
                                                "list": False,
                                                "load_from_db": False,
                                                "multiline": True,
                                                "name": "code",
                                                "password": False,
                                                "placeholder": "",
                                                "required": True,
                                                "show": True,
                                                "title_case": False,
                                                "type": "code",
                                                "value": "from pathlib import Path\n\nfrom langflow.base.data.utils import TEXT_FILE_TYPES, parse_text_file_to_data\nfrom langflow.custom import Component\nfrom langflow.io import BoolInput, FileInput, Output\nfrom langflow.schema import Data\n\n\nclass FileComponent(Component):\n    display_name = \"File\"\n    description = \"A generic file loader.\"\n    icon = \"file-text\"\n    name = \"File\"\n\n    inputs = [\n        FileInput(\n            name=\"path\",\n            display_name=\"Path\",\n            file_types=TEXT_FILE_TYPES,\n            info=f\"Supported file types: {', '.join(TEXT_FILE_TYPES)}\",\n        ),\n        BoolInput(\n            name=\"silent_errors\",\n            display_name=\"Silent Errors\",\n            advanced=True,\n            info=\"If true, errors will not raise an exception.\",\n        ),\n    ]\n\n    outputs = [\n        Output(display_name=\"Data\", name=\"data\", method=\"load_file\"),\n    ]\n\n    def load_file(self) -> Data:\n        if not self.path:\n            raise ValueError(\"Please, upload a file to use this component.\")\n        resolved_path = self.resolve_path(self.path)\n        silent_errors = self.silent_errors\n\n        extension = Path(resolved_path).suffix[1:].lower()\n\n        if extension == \"doc\":\n            raise ValueError(\"doc files are not supported. Please save as .docx\")\n        if extension not in TEXT_FILE_TYPES:\n            raise ValueError(f\"Unsupported file type: {extension}\")\n\n        data = parse_text_file_to_data(resolved_path, silent_errors)\n        self.status = data if data else \"No data\"\n        return data or Data()\n"
                                            },
                                            "path": {
                                                "advanced": False,
                                                "display_name": "Path",
                                                "dynamic": False,
                                                "fileTypes": [
                                                    "txt",
                                                    "md",
                                                    "mdx",
                                                    "csv",
                                                    "json",
                                                    "yaml",
                                                    "yml",
                                                    "xml",
                                                    "html",
                                                    "htm",
                                                    "pdf",
                                                    "docx",
                                                    "py",
                                                    "sh",
                                                    "sql",
                                                    "js",
                                                    "ts",
                                                    "tsx"
                                                ],
                                                "file_path": "",
                                                "info": "Supported file types: txt, md, mdx, csv, json, yaml, yml, xml, html, htm, pdf, docx, py, sh, sql, js, ts, tsx",
                                                "list": False,
                                                "name": "path",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "file",
                                                "value": ""
                                            },
                                            "silent_errors": {
                                                "advanced": True,
                                                "display_name": "Silent Errors",
                                                "dynamic": False,
                                                "info": "If true, errors will not raise an exception.",
                                                "list": False,
                                                "name": "silent_errors",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "bool",
                                                "value": False
                                            }
                                        }
                                    },
                                    "type": "File"
                                },
                                "dragging": False,
                                "height": 302,
                                "id": "File-TBV93",
                                "position": {
                                    "x": 1418.981990122179,
                                    "y": 1539.3825691184466
                                },
                                "positionAbsolute": {
                                    "x": 1418.981990122179,
                                    "y": 1539.3825691184466
                                },
                                "selected": False,
                                "type": "genericNode",
                                "width": 384
                            },
                            {
                                "data": {
                                    "description": "Implementation of Vector Store using Astra DB with search capabilities",
                                    "display_name": "Astra DB",
                                    "edited": False,
                                    "id": "AstraVectorStoreComponent-6hNSy",
                                    "node": {
                                        "base_classes": [
                                            "Data",
                                            "Retriever"
                                        ],
                                        "beta": False,
                                        "conditional_paths": [],
                                        "custom_fields": {},
                                        "description": "Implementation of Vector Store using Astra DB with search capabilities",
                                        "display_name": "Astra DB",
                                        "documentation": "https://python.langchain.com/docs/integrations/vectorstores/astradb",
                                        "edited": False,
                                        "field_order": [
                                            "collection_name",
                                            "token",
                                            "api_endpoint",
                                            "search_input",
                                            "ingest_data",
                                            "namespace",
                                            "metric",
                                            "batch_size",
                                            "bulk_insert_batch_concurrency",
                                            "bulk_insert_overwrite_concurrency",
                                            "bulk_delete_concurrency",
                                            "setup_mode",
                                            "pre_delete_collection",
                                            "metadata_indexing_include",
                                            "embedding",
                                            "metadata_indexing_exclude",
                                            "collection_indexing_policy",
                                            "number_of_results",
                                            "search_type",
                                            "search_score_threshold",
                                            "search_filter"
                                        ],
                                        "frozen": False,
                                        "icon": "AstraDB",
                                        "output_types": [],
                                        "outputs": [
                                            {
                                                "cache": True,
                                                "display_name": "Retriever",
                                                "method": "build_base_retriever",
                                                "name": "base_retriever",
                                                "selected": "Retriever",
                                                "types": [
                                                    "Retriever"
                                                ],
                                                "value": "__UNDEFINED__"
                                            },
                                            {
                                                "cache": True,
                                                "display_name": "Search Results",
                                                "method": "search_documents",
                                                "name": "search_results",
                                                "selected": "Data",
                                                "types": [
                                                    "Data"
                                                ],
                                                "value": "__UNDEFINED__"
                                            },
                                            {
                                                "cache": True,
                                                "display_name": "Vector Store",
                                                "method": "cast_vector_store",
                                                "name": "vector_store",
                                                "selected": "VectorStore",
                                                "types": [
                                                    "VectorStore"
                                                ],
                                                "value": "__UNDEFINED__"
                                            }
                                        ],
                                        "pinned": False,
                                        "template": {
                                            "_type": "Component",
                                            "api_endpoint": {
                                                "advanced": False,
                                                "display_name": "API Endpoint",
                                                "dynamic": False,
                                                "info": "API endpoint URL for the Astra DB service.",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "load_from_db": True,
                                                "name": "api_endpoint",
                                                "password": True,
                                                "placeholder": "",
                                                "required": True,
                                                "show": True,
                                                "title_case": False,
                                                "type": "str",
                                                "value": "ASTRA_DB_API_ENDPOINT"
                                            },
                                            "batch_size": {
                                                "advanced": True,
                                                "display_name": "Batch Size",
                                                "dynamic": False,
                                                "info": "Optional number of data to process in a single batch.",
                                                "list": False,
                                                "name": "batch_size",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "int",
                                                "value": ""
                                            },
                                            "bulk_delete_concurrency": {
                                                "advanced": True,
                                                "display_name": "Bulk Delete Concurrency",
                                                "dynamic": False,
                                                "info": "Optional concurrency level for bulk delete operations.",
                                                "list": False,
                                                "name": "bulk_delete_concurrency",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "int",
                                                "value": ""
                                            },
                                            "bulk_insert_batch_concurrency": {
                                                "advanced": True,
                                                "display_name": "Bulk Insert Batch Concurrency",
                                                "dynamic": False,
                                                "info": "Optional concurrency level for bulk insert operations.",
                                                "list": False,
                                                "name": "bulk_insert_batch_concurrency",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "int",
                                                "value": ""
                                            },
                                            "bulk_insert_overwrite_concurrency": {
                                                "advanced": True,
                                                "display_name": "Bulk Insert Overwrite Concurrency",
                                                "dynamic": False,
                                                "info": "Optional concurrency level for bulk insert operations that overwrite existing data.",
                                                "list": False,
                                                "name": "bulk_insert_overwrite_concurrency",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "int",
                                                "value": ""
                                            },
                                            "code": {
                                                "advanced": True,
                                                "dynamic": True,
                                                "fileTypes": [],
                                                "file_path": "",
                                                "info": "",
                                                "list": False,
                                                "load_from_db": False,
                                                "multiline": True,
                                                "name": "code",
                                                "password": False,
                                                "placeholder": "",
                                                "required": True,
                                                "show": True,
                                                "title_case": False,
                                                "type": "code",
                                                "value": "from loguru import logger\n\nfrom langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store\nfrom langflow.helpers import docs_to_data\nfrom langflow.inputs import DictInput, FloatInput\nfrom langflow.io import (\n    BoolInput,\n    DataInput,\n    DropdownInput,\n    HandleInput,\n    IntInput,\n    MultilineInput,\n    SecretStrInput,\n    StrInput,\n)\nfrom langflow.schema import Data\n\n\nclass AstraVectorStoreComponent(LCVectorStoreComponent):\n    display_name: str = \"Astra DB\"\n    description: str = \"Implementation of Vector Store using Astra DB with search capabilities\"\n    documentation: str = \"https://python.langchain.com/docs/integrations/vectorstores/astradb\"\n    name = \"AstraDB\"\n    icon: str = \"AstraDB\"\n\n    inputs = [\n        StrInput(\n            name=\"collection_name\",\n            display_name=\"Collection Name\",\n            info=\"The name of the collection within Astra DB where the vectors will be stored.\",\n            required=True,\n        ),\n        SecretStrInput(\n            name=\"token\",\n            display_name=\"Astra DB Application Token\",\n            info=\"Authentication token for accessing Astra DB.\",\n            value=\"ASTRA_DB_APPLICATION_TOKEN\",\n            required=True,\n        ),\n        SecretStrInput(\n            name=\"api_endpoint\",\n            display_name=\"API Endpoint\",\n            info=\"API endpoint URL for the Astra DB service.\",\n            value=\"ASTRA_DB_API_ENDPOINT\",\n            required=True,\n        ),\n        MultilineInput(\n            name=\"search_input\",\n            display_name=\"Search Input\",\n        ),\n        DataInput(\n            name=\"ingest_data\",\n            display_name=\"Ingest Data\",\n            is_list=True,\n        ),\n        StrInput(\n            name=\"namespace\",\n            display_name=\"Namespace\",\n            info=\"Optional namespace within Astra DB to use for the collection.\",\n            advanced=True,\n        ),\n        DropdownInput(\n            name=\"metric\",\n            display_name=\"Metric\",\n            info=\"Optional distance metric for vector comparisons in the vector store.\",\n            options=[\"cosine\", \"dot_product\", \"euclidean\"],\n            advanced=True,\n        ),\n        IntInput(\n            name=\"batch_size\",\n            display_name=\"Batch Size\",\n            info=\"Optional number of data to process in a single batch.\",\n            advanced=True,\n        ),\n        IntInput(\n            name=\"bulk_insert_batch_concurrency\",\n            display_name=\"Bulk Insert Batch Concurrency\",\n            info=\"Optional concurrency level for bulk insert operations.\",\n            advanced=True,\n        ),\n        IntInput(\n            name=\"bulk_insert_overwrite_concurrency\",\n            display_name=\"Bulk Insert Overwrite Concurrency\",\n            info=\"Optional concurrency level for bulk insert operations that overwrite existing data.\",\n            advanced=True,\n        ),\n        IntInput(\n            name=\"bulk_delete_concurrency\",\n            display_name=\"Bulk Delete Concurrency\",\n            info=\"Optional concurrency level for bulk delete operations.\",\n            advanced=True,\n        ),\n        DropdownInput(\n            name=\"setup_mode\",\n            display_name=\"Setup Mode\",\n            info=\"Configuration mode for setting up the vector store, with options like 'Sync', 'Async', or 'Off'.\",\n            options=[\"Sync\", \"Async\", \"Off\"],\n            advanced=True,\n            value=\"Sync\",\n        ),\n        BoolInput(\n            name=\"pre_delete_collection\",\n            display_name=\"Pre Delete Collection\",\n            info=\"Boolean flag to determine whether to delete the collection before creating a new one.\",\n            advanced=True,\n        ),\n        StrInput(\n            name=\"metadata_indexing_include\",\n            display_name=\"Metadata Indexing Include\",\n            info=\"Optional list of metadata fields to include in the indexing.\",\n            advanced=True,\n        ),\n        HandleInput(\n            name=\"embedding\",\n            display_name=\"Embedding or Astra Vectorize\",\n            input_types=[\"Embeddings\", \"dict\"],\n            info=\"Allows either an embedding model or an Astra Vectorize configuration.\",  # TODO: This should be optional, but need to refactor langchain-astradb first.\n        ),\n        StrInput(\n            name=\"metadata_indexing_exclude\",\n            display_name=\"Metadata Indexing Exclude\",\n            info=\"Optional list of metadata fields to exclude from the indexing.\",\n            advanced=True,\n        ),\n        StrInput(\n            name=\"collection_indexing_policy\",\n            display_name=\"Collection Indexing Policy\",\n            info=\"Optional dictionary defining the indexing policy for the collection.\",\n            advanced=True,\n        ),\n        IntInput(\n            name=\"number_of_results\",\n            display_name=\"Number of Results\",\n            info=\"Number of results to return.\",\n            advanced=True,\n            value=4,\n        ),\n        DropdownInput(\n            name=\"search_type\",\n            display_name=\"Search Type\",\n            info=\"Search type to use\",\n            options=[\"Similarity\", \"Similarity with score threshold\", \"MMR (Max Marginal Relevance)\"],\n            value=\"Similarity\",\n            advanced=True,\n        ),\n        FloatInput(\n            name=\"search_score_threshold\",\n            display_name=\"Search Score Threshold\",\n            info=\"Minimum similarity score threshold for search results. (when using 'Similarity with score threshold')\",\n            value=0,\n            advanced=True,\n        ),\n        DictInput(\n            name=\"search_filter\",\n            display_name=\"Search Metadata Filter\",\n            info=\"Optional dictionary of filters to apply to the search query.\",\n            advanced=True,\n            is_list=True,\n        ),\n    ]\n\n    @check_cached_vector_store\n    def build_vector_store(self):\n        try:\n            from langchain_astradb import AstraDBVectorStore\n            from langchain_astradb.utils.astradb import SetupMode\n        except ImportError:\n            raise ImportError(\n                \"Could not import langchain Astra DB integration package. \"\n                \"Please install it with `pip install langchain-astradb`.\"\n            )\n\n        try:\n            if not self.setup_mode:\n                self.setup_mode = self._inputs[\"setup_mode\"].options[0]\n\n            setup_mode_value = SetupMode[self.setup_mode.upper()]\n        except KeyError:\n            raise ValueError(f\"Invalid setup mode: {self.setup_mode}\")\n\n        if not isinstance(self.embedding, dict):\n            embedding_dict = {\"embedding\": self.embedding}\n        else:\n            from astrapy.info import CollectionVectorServiceOptions\n\n            dict_options = self.embedding.get(\"collection_vector_service_options\", {})\n            dict_options[\"authentication\"] = {\n                k: v for k, v in dict_options.get(\"authentication\", {}).items() if k and v\n            }\n            dict_options[\"parameters\"] = {k: v for k, v in dict_options.get(\"parameters\", {}).items() if k and v}\n            embedding_dict = {\n                \"collection_vector_service_options\": CollectionVectorServiceOptions.from_dict(dict_options)\n            }\n            collection_embedding_api_key = self.embedding.get(\"collection_embedding_api_key\")\n            if collection_embedding_api_key:\n                embedding_dict[\"collection_embedding_api_key\"] = collection_embedding_api_key\n\n        vector_store_kwargs = {\n            **embedding_dict,\n            \"collection_name\": self.collection_name,\n            \"token\": self.token,\n            \"api_endpoint\": self.api_endpoint,\n            \"namespace\": self.namespace or None,\n            \"metric\": self.metric or None,\n            \"batch_size\": self.batch_size or None,\n            \"bulk_insert_batch_concurrency\": self.bulk_insert_batch_concurrency or None,\n            \"bulk_insert_overwrite_concurrency\": self.bulk_insert_overwrite_concurrency or None,\n            \"bulk_delete_concurrency\": self.bulk_delete_concurrency or None,\n            \"setup_mode\": setup_mode_value,\n            \"pre_delete_collection\": self.pre_delete_collection or False,\n        }\n\n        if self.metadata_indexing_include:\n            vector_store_kwargs[\"metadata_indexing_include\"] = self.metadata_indexing_include\n        elif self.metadata_indexing_exclude:\n            vector_store_kwargs[\"metadata_indexing_exclude\"] = self.metadata_indexing_exclude\n        elif self.collection_indexing_policy:\n            vector_store_kwargs[\"collection_indexing_policy\"] = self.collection_indexing_policy\n\n        try:\n            vector_store = AstraDBVectorStore(**vector_store_kwargs)\n        except Exception as e:\n            raise ValueError(f\"Error initializing AstraDBVectorStore: {str(e)}\") from e\n\n        self._add_documents_to_vector_store(vector_store)\n        return vector_store\n\n    def _add_documents_to_vector_store(self, vector_store):\n        documents = []\n        for _input in self.ingest_data or []:\n            if isinstance(_input, Data):\n                documents.append(_input.to_lc_document())\n            else:\n                raise ValueError(\"Vector Store Inputs must be Data objects.\")\n\n        if documents:\n            logger.debug(f\"Adding {len(documents)} documents to the Vector Store.\")\n            try:\n                vector_store.add_documents(documents)\n            except Exception as e:\n                raise ValueError(f\"Error adding documents to AstraDBVectorStore: {str(e)}\") from e\n        else:\n            logger.debug(\"No documents to add to the Vector Store.\")\n\n    def _map_search_type(self):\n        if self.search_type == \"Similarity with score threshold\":\n            return \"similarity_score_threshold\"\n        elif self.search_type == \"MMR (Max Marginal Relevance)\":\n            return \"mmr\"\n        else:\n            return \"similarity\"\n\n    def _build_search_args(self):\n        args = {\n            \"k\": self.number_of_results,\n            \"score_threshold\": self.search_score_threshold,\n        }\n\n        if self.search_filter:\n            clean_filter = {k: v for k, v in self.search_filter.items() if k and v}\n            if len(clean_filter) > 0:\n                args[\"filter\"] = clean_filter\n        return args\n\n    def search_documents(self) -> list[Data]:\n        vector_store = self.build_vector_store()\n\n        logger.debug(f\"Search input: {self.search_input}\")\n        logger.debug(f\"Search type: {self.search_type}\")\n        logger.debug(f\"Number of results: {self.number_of_results}\")\n\n        if self.search_input and isinstance(self.search_input, str) and self.search_input.strip():\n            try:\n                search_type = self._map_search_type()\n                search_args = self._build_search_args()\n\n                docs = vector_store.search(query=self.search_input, search_type=search_type, **search_args)\n            except Exception as e:\n                raise ValueError(f\"Error performing search in AstraDBVectorStore: {str(e)}\") from e\n\n            logger.debug(f\"Retrieved documents: {len(docs)}\")\n\n            data = docs_to_data(docs)\n            logger.debug(f\"Converted documents to data: {len(data)}\")\n            self.status = data\n            return data\n        else:\n            logger.debug(\"No search input provided. Skipping search.\")\n            return []\n\n    def get_retriever_kwargs(self):\n        search_args = self._build_search_args()\n        return {\n            \"search_type\": self._map_search_type(),\n            \"search_kwargs\": search_args,\n        }\n"
                                            },
                                            "collection_indexing_policy": {
                                                "advanced": True,
                                                "display_name": "Collection Indexing Policy",
                                                "dynamic": False,
                                                "info": "Optional dictionary defining the indexing policy for the collection.",
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "collection_indexing_policy",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "collection_name": {
                                                "advanced": False,
                                                "display_name": "Collection Name",
                                                "dynamic": False,
                                                "info": "The name of the collection within Astra DB where the vectors will be stored.",
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "collection_name",
                                                "placeholder": "",
                                                "required": True,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": "langflow"
                                            },
                                            "embedding": {
                                                "advanced": False,
                                                "display_name": "Embedding or Astra Vectorize",
                                                "dynamic": False,
                                                "info": "Allows either an embedding model or an Astra Vectorize configuration.",
                                                "input_types": [
                                                    "Embeddings",
                                                    "dict"
                                                ],
                                                "list": False,
                                                "name": "embedding",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "other",
                                                "value": ""
                                            },
                                            "ingest_data": {
                                                "advanced": False,
                                                "display_name": "Ingest Data",
                                                "dynamic": False,
                                                "info": "",
                                                "input_types": [
                                                    "Data"
                                                ],
                                                "list": True,
                                                "name": "ingest_data",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "other",
                                                "value": ""
                                            },
                                            "metadata_indexing_exclude": {
                                                "advanced": True,
                                                "display_name": "Metadata Indexing Exclude",
                                                "dynamic": False,
                                                "info": "Optional list of metadata fields to exclude from the indexing.",
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "metadata_indexing_exclude",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "metadata_indexing_include": {
                                                "advanced": True,
                                                "display_name": "Metadata Indexing Include",
                                                "dynamic": False,
                                                "info": "Optional list of metadata fields to include in the indexing.",
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "metadata_indexing_include",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "metric": {
                                                "advanced": True,
                                                "display_name": "Metric",
                                                "dynamic": False,
                                                "info": "Optional distance metric for vector comparisons in the vector store.",
                                                "name": "metric",
                                                "options": [
                                                    "cosine",
                                                    "dot_product",
                                                    "euclidean"
                                                ],
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "namespace": {
                                                "advanced": True,
                                                "display_name": "Namespace",
                                                "dynamic": False,
                                                "info": "Optional namespace within Astra DB to use for the collection.",
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "namespace",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "number_of_results": {
                                                "advanced": True,
                                                "display_name": "Number of Results",
                                                "dynamic": False,
                                                "info": "Number of results to return.",
                                                "list": False,
                                                "name": "number_of_results",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "int",
                                                "value": 4
                                            },
                                            "pre_delete_collection": {
                                                "advanced": True,
                                                "display_name": "Pre Delete Collection",
                                                "dynamic": False,
                                                "info": "Boolean flag to determine whether to delete the collection before creating a new one.",
                                                "list": False,
                                                "name": "pre_delete_collection",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "bool",
                                                "value": False
                                            },
                                            "search_filter": {
                                                "advanced": True,
                                                "display_name": "Search Metadata Filter",
                                                "dynamic": False,
                                                "info": "Optional dictionary of filters to apply to the search query.",
                                                "list": True,
                                                "name": "search_filter",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "type": "dict",
                                                "value": {}
                                            },
                                            "search_input": {
                                                "advanced": False,
                                                "display_name": "Search Input",
                                                "dynamic": False,
                                                "info": "",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "list": False,
                                                "load_from_db": False,
                                                "multiline": True,
                                                "name": "search_input",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "search_score_threshold": {
                                                "advanced": True,
                                                "display_name": "Search Score Threshold",
                                                "dynamic": False,
                                                "info": "Minimum similarity score threshold for search results. (when using 'Similarity with score threshold')",
                                                "list": False,
                                                "name": "search_score_threshold",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "float",
                                                "value": 0
                                            },
                                            "search_type": {
                                                "advanced": True,
                                                "display_name": "Search Type",
                                                "dynamic": False,
                                                "info": "Search type to use",
                                                "name": "search_type",
                                                "options": [
                                                    "Similarity",
                                                    "Similarity with score threshold",
                                                    "MMR (Max Marginal Relevance)"
                                                ],
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": "Similarity"
                                            },
                                            "setup_mode": {
                                                "advanced": True,
                                                "display_name": "Setup Mode",
                                                "dynamic": False,
                                                "info": "Configuration mode for setting up the vector store, with options like 'Sync', 'Async', or 'Off'.",
                                                "name": "setup_mode",
                                                "options": [
                                                    "Sync",
                                                    "Async",
                                                    "Off"
                                                ],
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": "Sync"
                                            },
                                            "token": {
                                                "advanced": False,
                                                "display_name": "Astra DB Application Token",
                                                "dynamic": False,
                                                "info": "Authentication token for accessing Astra DB.",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "load_from_db": True,
                                                "name": "token",
                                                "password": True,
                                                "placeholder": "",
                                                "required": True,
                                                "show": True,
                                                "title_case": False,
                                                "type": "str",
                                                "value": "ASTRA_DB_APPLICATION_TOKEN"
                                            }
                                        }
                                    },
                                    "type": "AstraVectorStoreComponent"
                                },
                                "dragging": False,
                                "height": 774,
                                "id": "AstraVectorStoreComponent-6hNSy",
                                "position": {
                                    "x": 2678.506138892635,
                                    "y": 1267.3353646037478
                                },
                                "positionAbsolute": {
                                    "x": 2678.506138892635,
                                    "y": 1267.3353646037478
                                },
                                "selected": False,
                                "type": "genericNode",
                                "width": 384
                            },
                            {
                                "data": {
                                    "description": "Generate embeddings using OpenAI models.",
                                    "display_name": "OpenAI Embeddings",
                                    "id": "OpenAIEmbeddings-hLfqb",
                                    "node": {
                                        "base_classes": [
                                            "Embeddings"
                                        ],
                                        "beta": False,
                                        "conditional_paths": [],
                                        "custom_fields": {},
                                        "description": "Generate embeddings using OpenAI models.",
                                        "display_name": "OpenAI Embeddings",
                                        "documentation": "",
                                        "edited": False,
                                        "field_order": [
                                            "default_headers",
                                            "default_query",
                                            "chunk_size",
                                            "client",
                                            "deployment",
                                            "embedding_ctx_length",
                                            "max_retries",
                                            "model",
                                            "model_kwargs",
                                            "openai_api_base",
                                            "openai_api_key",
                                            "openai_api_type",
                                            "openai_api_version",
                                            "openai_organization",
                                            "openai_proxy",
                                            "request_timeout",
                                            "show_progress_bar",
                                            "skip_empty",
                                            "tiktoken_model_name",
                                            "tiktoken_enable",
                                            "dimensions"
                                        ],
                                        "frozen": False,
                                        "icon": "OpenAI",
                                        "output_types": [],
                                        "outputs": [
                                            {
                                                "cache": True,
                                                "display_name": "Embeddings",
                                                "method": "build_embeddings",
                                                "name": "embeddings",
                                                "selected": "Embeddings",
                                                "types": [
                                                    "Embeddings"
                                                ],
                                                "value": "__UNDEFINED__"
                                            }
                                        ],
                                        "pinned": False,
                                        "template": {
                                            "_type": "Component",
                                            "chunk_size": {
                                                "advanced": True,
                                                "display_name": "Chunk Size",
                                                "dynamic": False,
                                                "info": "",
                                                "list": False,
                                                "name": "chunk_size",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "int",
                                                "value": 1000
                                            },
                                            "client": {
                                                "advanced": True,
                                                "display_name": "Client",
                                                "dynamic": False,
                                                "info": "",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "client",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "code": {
                                                "advanced": True,
                                                "dynamic": True,
                                                "fileTypes": [],
                                                "file_path": "",
                                                "info": "",
                                                "list": False,
                                                "load_from_db": False,
                                                "multiline": True,
                                                "name": "code",
                                                "password": False,
                                                "placeholder": "",
                                                "required": True,
                                                "show": True,
                                                "title_case": False,
                                                "type": "code",
                                                "value": "from langchain_openai.embeddings.base import OpenAIEmbeddings\n\nfrom langflow.base.embeddings.model import LCEmbeddingsModel\nfrom langflow.base.models.openai_constants import OPENAI_EMBEDDING_MODEL_NAMES\nfrom langflow.field_typing import Embeddings\nfrom langflow.io import BoolInput, DictInput, DropdownInput, FloatInput, IntInput, MessageTextInput, SecretStrInput\n\n\nclass OpenAIEmbeddingsComponent(LCEmbeddingsModel):\n    display_name = \"OpenAI Embeddings\"\n    description = \"Generate embeddings using OpenAI models.\"\n    icon = \"OpenAI\"\n    name = \"OpenAIEmbeddings\"\n\n    inputs = [\n        DictInput(\n            name=\"default_headers\",\n            display_name=\"Default Headers\",\n            advanced=True,\n            info=\"Default headers to use for the API request.\",\n        ),\n        DictInput(\n            name=\"default_query\",\n            display_name=\"Default Query\",\n            advanced=True,\n            info=\"Default query parameters to use for the API request.\",\n        ),\n        IntInput(name=\"chunk_size\", display_name=\"Chunk Size\", advanced=True, value=1000),\n        MessageTextInput(name=\"client\", display_name=\"Client\", advanced=True),\n        MessageTextInput(name=\"deployment\", display_name=\"Deployment\", advanced=True),\n        IntInput(name=\"embedding_ctx_length\", display_name=\"Embedding Context Length\", advanced=True, value=1536),\n        IntInput(name=\"max_retries\", display_name=\"Max Retries\", value=3, advanced=True),\n        DropdownInput(\n            name=\"model\",\n            display_name=\"Model\",\n            advanced=False,\n            options=OPENAI_EMBEDDING_MODEL_NAMES,\n            value=\"text-embedding-3-small\",\n        ),\n        DictInput(name=\"model_kwargs\", display_name=\"Model Kwargs\", advanced=True),\n        SecretStrInput(name=\"openai_api_base\", display_name=\"OpenAI API Base\", advanced=True),\n        SecretStrInput(name=\"openai_api_key\", display_name=\"OpenAI API Key\", value=\"OPENAI_API_KEY\"),\n        SecretStrInput(name=\"openai_api_type\", display_name=\"OpenAI API Type\", advanced=True),\n        MessageTextInput(name=\"openai_api_version\", display_name=\"OpenAI API Version\", advanced=True),\n        MessageTextInput(\n            name=\"openai_organization\",\n            display_name=\"OpenAI Organization\",\n            advanced=True,\n        ),\n        MessageTextInput(name=\"openai_proxy\", display_name=\"OpenAI Proxy\", advanced=True),\n        FloatInput(name=\"request_timeout\", display_name=\"Request Timeout\", advanced=True),\n        BoolInput(name=\"show_progress_bar\", display_name=\"Show Progress Bar\", advanced=True),\n        BoolInput(name=\"skip_empty\", display_name=\"Skip Empty\", advanced=True),\n        MessageTextInput(\n            name=\"tiktoken_model_name\",\n            display_name=\"TikToken Model Name\",\n            advanced=True,\n        ),\n        BoolInput(\n            name=\"tiktoken_enable\",\n            display_name=\"TikToken Enable\",\n            advanced=True,\n            value=True,\n            info=\"If False, you must have transformers installed.\",\n        ),\n        IntInput(\n            name=\"dimensions\",\n            display_name=\"Dimensions\",\n            info=\"The number of dimensions the resulting output embeddings should have. Only supported by certain models.\",\n            advanced=True,\n        ),\n    ]\n\n    def build_embeddings(self) -> Embeddings:\n        return OpenAIEmbeddings(\n            tiktoken_enabled=self.tiktoken_enable,\n            default_headers=self.default_headers,\n            default_query=self.default_query,\n            allowed_special=\"all\",\n            disallowed_special=\"all\",\n            chunk_size=self.chunk_size,\n            deployment=self.deployment,\n            embedding_ctx_length=self.embedding_ctx_length,\n            max_retries=self.max_retries,\n            model=self.model,\n            model_kwargs=self.model_kwargs,\n            base_url=self.openai_api_base,\n            api_key=self.openai_api_key,\n            openai_api_type=self.openai_api_type,\n            api_version=self.openai_api_version,\n            organization=self.openai_organization,\n            openai_proxy=self.openai_proxy,\n            timeout=self.request_timeout or None,\n            show_progress_bar=self.show_progress_bar,\n            skip_empty=self.skip_empty,\n            tiktoken_model_name=self.tiktoken_model_name,\n            dimensions=self.dimensions or None,\n        )\n"
                                            },
                                            "default_headers": {
                                                "advanced": True,
                                                "display_name": "Default Headers",
                                                "dynamic": False,
                                                "info": "Default headers to use for the API request.",
                                                "list": False,
                                                "name": "default_headers",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "type": "dict",
                                                "value": {}
                                            },
                                            "default_query": {
                                                "advanced": True,
                                                "display_name": "Default Query",
                                                "dynamic": False,
                                                "info": "Default query parameters to use for the API request.",
                                                "list": False,
                                                "name": "default_query",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "type": "dict",
                                                "value": {}
                                            },
                                            "deployment": {
                                                "advanced": True,
                                                "display_name": "Deployment",
                                                "dynamic": False,
                                                "info": "",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "deployment",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "dimensions": {
                                                "advanced": True,
                                                "display_name": "Dimensions",
                                                "dynamic": False,
                                                "info": "The number of dimensions the resulting output embeddings should have. Only supported by certain models.",
                                                "list": False,
                                                "name": "dimensions",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "int",
                                                "value": ""
                                            },
                                            "embedding_ctx_length": {
                                                "advanced": True,
                                                "display_name": "Embedding Context Length",
                                                "dynamic": False,
                                                "info": "",
                                                "list": False,
                                                "name": "embedding_ctx_length",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "int",
                                                "value": 1536
                                            },
                                            "max_retries": {
                                                "advanced": True,
                                                "display_name": "Max Retries",
                                                "dynamic": False,
                                                "info": "",
                                                "list": False,
                                                "name": "max_retries",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "int",
                                                "value": 3
                                            },
                                            "model": {
                                                "advanced": False,
                                                "display_name": "Model",
                                                "dynamic": False,
                                                "info": "",
                                                "name": "model",
                                                "options": [
                                                    "text-embedding-3-small",
                                                    "text-embedding-3-large",
                                                    "text-embedding-ada-002"
                                                ],
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": "text-embedding-3-small"
                                            },
                                            "model_kwargs": {
                                                "advanced": True,
                                                "display_name": "Model Kwargs",
                                                "dynamic": False,
                                                "info": "",
                                                "list": False,
                                                "name": "model_kwargs",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "type": "dict",
                                                "value": {}
                                            },
                                            "openai_api_base": {
                                                "advanced": True,
                                                "display_name": "OpenAI API Base",
                                                "dynamic": False,
                                                "info": "",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "load_from_db": True,
                                                "name": "openai_api_base",
                                                "password": True,
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "openai_api_key": {
                                                "advanced": False,
                                                "display_name": "OpenAI API Key",
                                                "dynamic": False,
                                                "info": "",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "load_from_db": True,
                                                "name": "openai_api_key",
                                                "password": True,
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "type": "str",
                                                "value": "OPENAI_API_KEY"
                                            },
                                            "openai_api_type": {
                                                "advanced": True,
                                                "display_name": "OpenAI API Type",
                                                "dynamic": False,
                                                "info": "",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "load_from_db": True,
                                                "name": "openai_api_type",
                                                "password": True,
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "openai_api_version": {
                                                "advanced": True,
                                                "display_name": "OpenAI API Version",
                                                "dynamic": False,
                                                "info": "",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "openai_api_version",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "openai_organization": {
                                                "advanced": True,
                                                "display_name": "OpenAI Organization",
                                                "dynamic": False,
                                                "info": "",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "openai_organization",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "openai_proxy": {
                                                "advanced": True,
                                                "display_name": "OpenAI Proxy",
                                                "dynamic": False,
                                                "info": "",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "openai_proxy",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "request_timeout": {
                                                "advanced": True,
                                                "display_name": "Request Timeout",
                                                "dynamic": False,
                                                "info": "",
                                                "list": False,
                                                "name": "request_timeout",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "float",
                                                "value": ""
                                            },
                                            "show_progress_bar": {
                                                "advanced": True,
                                                "display_name": "Show Progress Bar",
                                                "dynamic": False,
                                                "info": "",
                                                "list": False,
                                                "name": "show_progress_bar",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "bool",
                                                "value": False
                                            },
                                            "skip_empty": {
                                                "advanced": True,
                                                "display_name": "Skip Empty",
                                                "dynamic": False,
                                                "info": "",
                                                "list": False,
                                                "name": "skip_empty",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "bool",
                                                "value": False
                                            },
                                            "tiktoken_enable": {
                                                "advanced": True,
                                                "display_name": "TikToken Enable",
                                                "dynamic": False,
                                                "info": "If False, you must have transformers installed.",
                                                "list": False,
                                                "name": "tiktoken_enable",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "bool",
                                                "value": True
                                            },
                                            "tiktoken_model_name": {
                                                "advanced": True,
                                                "display_name": "TikToken Model Name",
                                                "dynamic": False,
                                                "info": "",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "tiktoken_model_name",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            }
                                        }
                                    },
                                    "type": "OpenAIEmbeddings"
                                },
                                "dragging": False,
                                "height": 388,
                                "id": "OpenAIEmbeddings-hLfqb",
                                "position": {
                                    "x": 2044.683126356786,
                                    "y": 1785.2283494456522
                                },
                                "positionAbsolute": {
                                    "x": 2044.683126356786,
                                    "y": 1785.2283494456522
                                },
                                "selected": False,
                                "type": "genericNode",
                                "width": 384
                            },
                            {
                                "data": {
                                    "description": "Generate embeddings using OpenAI models.",
                                    "display_name": "OpenAI Embeddings",
                                    "id": "OpenAIEmbeddings-OhWJM",
                                    "node": {
                                        "base_classes": [
                                            "Embeddings"
                                        ],
                                        "beta": False,
                                        "conditional_paths": [],
                                        "custom_fields": {},
                                        "description": "Generate embeddings using OpenAI models.",
                                        "display_name": "OpenAI Embeddings",
                                        "documentation": "",
                                        "edited": False,
                                        "field_order": [
                                            "default_headers",
                                            "default_query",
                                            "chunk_size",
                                            "client",
                                            "deployment",
                                            "embedding_ctx_length",
                                            "max_retries",
                                            "model",
                                            "model_kwargs",
                                            "openai_api_base",
                                            "openai_api_key",
                                            "openai_api_type",
                                            "openai_api_version",
                                            "openai_organization",
                                            "openai_proxy",
                                            "request_timeout",
                                            "show_progress_bar",
                                            "skip_empty",
                                            "tiktoken_model_name",
                                            "tiktoken_enable",
                                            "dimensions"
                                        ],
                                        "frozen": False,
                                        "icon": "OpenAI",
                                        "output_types": [],
                                        "outputs": [
                                            {
                                                "cache": True,
                                                "display_name": "Embeddings",
                                                "method": "build_embeddings",
                                                "name": "embeddings",
                                                "selected": "Embeddings",
                                                "types": [
                                                    "Embeddings"
                                                ],
                                                "value": "__UNDEFINED__"
                                            }
                                        ],
                                        "pinned": False,
                                        "template": {
                                            "_type": "Component",
                                            "chunk_size": {
                                                "advanced": True,
                                                "display_name": "Chunk Size",
                                                "dynamic": False,
                                                "info": "",
                                                "list": False,
                                                "name": "chunk_size",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "int",
                                                "value": 1000
                                            },
                                            "client": {
                                                "advanced": True,
                                                "display_name": "Client",
                                                "dynamic": False,
                                                "info": "",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "client",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "code": {
                                                "advanced": True,
                                                "dynamic": True,
                                                "fileTypes": [],
                                                "file_path": "",
                                                "info": "",
                                                "list": False,
                                                "load_from_db": False,
                                                "multiline": True,
                                                "name": "code",
                                                "password": False,
                                                "placeholder": "",
                                                "required": True,
                                                "show": True,
                                                "title_case": False,
                                                "type": "code",
                                                "value": "from langchain_openai.embeddings.base import OpenAIEmbeddings\n\nfrom langflow.base.embeddings.model import LCEmbeddingsModel\nfrom langflow.base.models.openai_constants import OPENAI_EMBEDDING_MODEL_NAMES\nfrom langflow.field_typing import Embeddings\nfrom langflow.io import BoolInput, DictInput, DropdownInput, FloatInput, IntInput, MessageTextInput, SecretStrInput\n\n\nclass OpenAIEmbeddingsComponent(LCEmbeddingsModel):\n    display_name = \"OpenAI Embeddings\"\n    description = \"Generate embeddings using OpenAI models.\"\n    icon = \"OpenAI\"\n    name = \"OpenAIEmbeddings\"\n\n    inputs = [\n        DictInput(\n            name=\"default_headers\",\n            display_name=\"Default Headers\",\n            advanced=True,\n            info=\"Default headers to use for the API request.\",\n        ),\n        DictInput(\n            name=\"default_query\",\n            display_name=\"Default Query\",\n            advanced=True,\n            info=\"Default query parameters to use for the API request.\",\n        ),\n        IntInput(name=\"chunk_size\", display_name=\"Chunk Size\", advanced=True, value=1000),\n        MessageTextInput(name=\"client\", display_name=\"Client\", advanced=True),\n        MessageTextInput(name=\"deployment\", display_name=\"Deployment\", advanced=True),\n        IntInput(name=\"embedding_ctx_length\", display_name=\"Embedding Context Length\", advanced=True, value=1536),\n        IntInput(name=\"max_retries\", display_name=\"Max Retries\", value=3, advanced=True),\n        DropdownInput(\n            name=\"model\",\n            display_name=\"Model\",\n            advanced=False,\n            options=OPENAI_EMBEDDING_MODEL_NAMES,\n            value=\"text-embedding-3-small\",\n        ),\n        DictInput(name=\"model_kwargs\", display_name=\"Model Kwargs\", advanced=True),\n        SecretStrInput(name=\"openai_api_base\", display_name=\"OpenAI API Base\", advanced=True),\n        SecretStrInput(name=\"openai_api_key\", display_name=\"OpenAI API Key\", value=\"OPENAI_API_KEY\"),\n        SecretStrInput(name=\"openai_api_type\", display_name=\"OpenAI API Type\", advanced=True),\n        MessageTextInput(name=\"openai_api_version\", display_name=\"OpenAI API Version\", advanced=True),\n        MessageTextInput(\n            name=\"openai_organization\",\n            display_name=\"OpenAI Organization\",\n            advanced=True,\n        ),\n        MessageTextInput(name=\"openai_proxy\", display_name=\"OpenAI Proxy\", advanced=True),\n        FloatInput(name=\"request_timeout\", display_name=\"Request Timeout\", advanced=True),\n        BoolInput(name=\"show_progress_bar\", display_name=\"Show Progress Bar\", advanced=True),\n        BoolInput(name=\"skip_empty\", display_name=\"Skip Empty\", advanced=True),\n        MessageTextInput(\n            name=\"tiktoken_model_name\",\n            display_name=\"TikToken Model Name\",\n            advanced=True,\n        ),\n        BoolInput(\n            name=\"tiktoken_enable\",\n            display_name=\"TikToken Enable\",\n            advanced=True,\n            value=True,\n            info=\"If False, you must have transformers installed.\",\n        ),\n        IntInput(\n            name=\"dimensions\",\n            display_name=\"Dimensions\",\n            info=\"The number of dimensions the resulting output embeddings should have. Only supported by certain models.\",\n            advanced=True,\n        ),\n    ]\n\n    def build_embeddings(self) -> Embeddings:\n        return OpenAIEmbeddings(\n            tiktoken_enabled=self.tiktoken_enable,\n            default_headers=self.default_headers,\n            default_query=self.default_query,\n            allowed_special=\"all\",\n            disallowed_special=\"all\",\n            chunk_size=self.chunk_size,\n            deployment=self.deployment,\n            embedding_ctx_length=self.embedding_ctx_length,\n            max_retries=self.max_retries,\n            model=self.model,\n            model_kwargs=self.model_kwargs,\n            base_url=self.openai_api_base,\n            api_key=self.openai_api_key,\n            openai_api_type=self.openai_api_type,\n            api_version=self.openai_api_version,\n            organization=self.openai_organization,\n            openai_proxy=self.openai_proxy,\n            timeout=self.request_timeout or None,\n            show_progress_bar=self.show_progress_bar,\n            skip_empty=self.skip_empty,\n            tiktoken_model_name=self.tiktoken_model_name,\n            dimensions=self.dimensions or None,\n        )\n"
                                            },
                                            "default_headers": {
                                                "advanced": True,
                                                "display_name": "Default Headers",
                                                "dynamic": False,
                                                "info": "Default headers to use for the API request.",
                                                "list": False,
                                                "name": "default_headers",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "type": "dict",
                                                "value": {}
                                            },
                                            "default_query": {
                                                "advanced": True,
                                                "display_name": "Default Query",
                                                "dynamic": False,
                                                "info": "Default query parameters to use for the API request.",
                                                "list": False,
                                                "name": "default_query",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "type": "dict",
                                                "value": {}
                                            },
                                            "deployment": {
                                                "advanced": True,
                                                "display_name": "Deployment",
                                                "dynamic": False,
                                                "info": "",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "deployment",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "dimensions": {
                                                "advanced": True,
                                                "display_name": "Dimensions",
                                                "dynamic": False,
                                                "info": "The number of dimensions the resulting output embeddings should have. Only supported by certain models.",
                                                "list": False,
                                                "name": "dimensions",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "int",
                                                "value": ""
                                            },
                                            "embedding_ctx_length": {
                                                "advanced": True,
                                                "display_name": "Embedding Context Length",
                                                "dynamic": False,
                                                "info": "",
                                                "list": False,
                                                "name": "embedding_ctx_length",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "int",
                                                "value": 1536
                                            },
                                            "max_retries": {
                                                "advanced": True,
                                                "display_name": "Max Retries",
                                                "dynamic": False,
                                                "info": "",
                                                "list": False,
                                                "name": "max_retries",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "int",
                                                "value": 3
                                            },
                                            "model": {
                                                "advanced": False,
                                                "display_name": "Model",
                                                "dynamic": False,
                                                "info": "",
                                                "name": "model",
                                                "options": [
                                                    "text-embedding-3-small",
                                                    "text-embedding-3-large",
                                                    "text-embedding-ada-002"
                                                ],
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": "text-embedding-3-small"
                                            },
                                            "model_kwargs": {
                                                "advanced": True,
                                                "display_name": "Model Kwargs",
                                                "dynamic": False,
                                                "info": "",
                                                "list": False,
                                                "name": "model_kwargs",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "type": "dict",
                                                "value": {}
                                            },
                                            "openai_api_base": {
                                                "advanced": True,
                                                "display_name": "OpenAI API Base",
                                                "dynamic": False,
                                                "info": "",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "load_from_db": True,
                                                "name": "openai_api_base",
                                                "password": True,
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "openai_api_key": {
                                                "advanced": False,
                                                "display_name": "OpenAI API Key",
                                                "dynamic": False,
                                                "info": "",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "load_from_db": True,
                                                "name": "openai_api_key",
                                                "password": True,
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "type": "str",
                                                "value": "OPENAI_API_KEY"
                                            },
                                            "openai_api_type": {
                                                "advanced": True,
                                                "display_name": "OpenAI API Type",
                                                "dynamic": False,
                                                "info": "",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "load_from_db": True,
                                                "name": "openai_api_type",
                                                "password": True,
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "openai_api_version": {
                                                "advanced": True,
                                                "display_name": "OpenAI API Version",
                                                "dynamic": False,
                                                "info": "",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "openai_api_version",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "openai_organization": {
                                                "advanced": True,
                                                "display_name": "OpenAI Organization",
                                                "dynamic": False,
                                                "info": "",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "openai_organization",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "openai_proxy": {
                                                "advanced": True,
                                                "display_name": "OpenAI Proxy",
                                                "dynamic": False,
                                                "info": "",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "openai_proxy",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "request_timeout": {
                                                "advanced": True,
                                                "display_name": "Request Timeout",
                                                "dynamic": False,
                                                "info": "",
                                                "list": False,
                                                "name": "request_timeout",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "float",
                                                "value": ""
                                            },
                                            "show_progress_bar": {
                                                "advanced": True,
                                                "display_name": "Show Progress Bar",
                                                "dynamic": False,
                                                "info": "",
                                                "list": False,
                                                "name": "show_progress_bar",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "bool",
                                                "value": False
                                            },
                                            "skip_empty": {
                                                "advanced": True,
                                                "display_name": "Skip Empty",
                                                "dynamic": False,
                                                "info": "",
                                                "list": False,
                                                "name": "skip_empty",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "bool",
                                                "value": False
                                            },
                                            "tiktoken_enable": {
                                                "advanced": True,
                                                "display_name": "TikToken Enable",
                                                "dynamic": False,
                                                "info": "If False, you must have transformers installed.",
                                                "list": False,
                                                "name": "tiktoken_enable",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "bool",
                                                "value": True
                                            },
                                            "tiktoken_model_name": {
                                                "advanced": True,
                                                "display_name": "TikToken Model Name",
                                                "dynamic": False,
                                                "info": "",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "tiktoken_model_name",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            }
                                        }
                                    },
                                    "type": "OpenAIEmbeddings"
                                },
                                "dragging": False,
                                "height": 388,
                                "id": "OpenAIEmbeddings-OhWJM",
                                "position": {
                                    "x": 628.9252513328779,
                                    "y": 648.6750537749285
                                },
                                "positionAbsolute": {
                                    "x": 628.9252513328779,
                                    "y": 648.6750537749285
                                },
                                "selected": False,
                                "type": "genericNode",
                                "width": 384
                            },
                            {
                                "data": {
                                    "description": "Generates text using OpenAI LLMs.",
                                    "display_name": "OpenAI",
                                    "id": "OpenAIModel-ExXPZ",
                                    "node": {
                                        "base_classes": [
                                            "LanguageModel",
                                            "Message"
                                        ],
                                        "beta": False,
                                        "conditional_paths": [],
                                        "custom_fields": {},
                                        "description": "Generates text using OpenAI LLMs.",
                                        "display_name": "OpenAI",
                                        "documentation": "",
                                        "edited": False,
                                        "field_order": [
                                            "input_value",
                                            "system_message",
                                            "stream",
                                            "max_tokens",
                                            "model_kwargs",
                                            "json_mode",
                                            "output_schema",
                                            "model_name",
                                            "openai_api_base",
                                            "api_key",
                                            "temperature",
                                            "seed"
                                        ],
                                        "frozen": False,
                                        "icon": "OpenAI",
                                        "output_types": [],
                                        "outputs": [
                                            {
                                                "cache": True,
                                                "display_name": "Text",
                                                "method": "text_response",
                                                "name": "text_output",
                                                "selected": "Message",
                                                "types": [
                                                    "Message"
                                                ],
                                                "value": "__UNDEFINED__"
                                            },
                                            {
                                                "cache": True,
                                                "display_name": "Language Model",
                                                "method": "build_model",
                                                "name": "model_output",
                                                "selected": "LanguageModel",
                                                "types": [
                                                    "LanguageModel"
                                                ],
                                                "value": "__UNDEFINED__"
                                            }
                                        ],
                                        "pinned": False,
                                        "template": {
                                            "_type": "Component",
                                            "api_key": {
                                                "advanced": False,
                                                "display_name": "OpenAI API Key",
                                                "dynamic": False,
                                                "info": "The OpenAI API Key to use for the OpenAI model.",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "load_from_db": True,
                                                "name": "api_key",
                                                "password": True,
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "type": "str",
                                                "value": "OPENAI_API_KEY"
                                            },
                                            "code": {
                                                "advanced": True,
                                                "dynamic": True,
                                                "fileTypes": [],
                                                "file_path": "",
                                                "info": "",
                                                "list": False,
                                                "load_from_db": False,
                                                "multiline": True,
                                                "name": "code",
                                                "password": False,
                                                "placeholder": "",
                                                "required": True,
                                                "show": True,
                                                "title_case": False,
                                                "type": "code",
                                                "value": "import operator\nfrom functools import reduce\n\nfrom langflow.field_typing.range_spec import RangeSpec\nfrom langchain_openai import ChatOpenAI\nfrom pydantic.v1 import SecretStr\n\nfrom langflow.base.models.model import LCModelComponent\nfrom langflow.base.models.openai_constants import OPENAI_MODEL_NAMES\nfrom langflow.field_typing import LanguageModel\nfrom langflow.inputs import (\n    BoolInput,\n    DictInput,\n    DropdownInput,\n    FloatInput,\n    IntInput,\n    SecretStrInput,\n    StrInput,\n)\n\n\nclass OpenAIModelComponent(LCModelComponent):\n    display_name = \"OpenAI\"\n    description = \"Generates text using OpenAI LLMs.\"\n    icon = \"OpenAI\"\n    name = \"OpenAIModel\"\n\n    inputs = LCModelComponent._base_inputs + [\n        IntInput(\n            name=\"max_tokens\",\n            display_name=\"Max Tokens\",\n            advanced=True,\n            info=\"The maximum number of tokens to generate. Set to 0 for unlimited tokens.\",\n            range_spec=RangeSpec(min=0, max=128000),\n        ),\n        DictInput(name=\"model_kwargs\", display_name=\"Model Kwargs\", advanced=True),\n        BoolInput(\n            name=\"json_mode\",\n            display_name=\"JSON Mode\",\n            advanced=True,\n            info=\"If True, it will output JSON regardless of passing a schema.\",\n        ),\n        DictInput(\n            name=\"output_schema\",\n            is_list=True,\n            display_name=\"Schema\",\n            advanced=True,\n            info=\"The schema for the Output of the model. You must pass the word JSON in the prompt. If left blank, JSON mode will be disabled.\",\n        ),\n        DropdownInput(\n            name=\"model_name\",\n            display_name=\"Model Name\",\n            advanced=False,\n            options=OPENAI_MODEL_NAMES,\n            value=OPENAI_MODEL_NAMES[0],\n        ),\n        StrInput(\n            name=\"openai_api_base\",\n            display_name=\"OpenAI API Base\",\n            advanced=True,\n            info=\"The base URL of the OpenAI API. Defaults to https://api.openai.com/v1. You can change this to use other APIs like JinaChat, LocalAI and Prem.\",\n        ),\n        SecretStrInput(\n            name=\"api_key\",\n            display_name=\"OpenAI API Key\",\n            info=\"The OpenAI API Key to use for the OpenAI model.\",\n            advanced=False,\n            value=\"OPENAI_API_KEY\",\n        ),\n        FloatInput(name=\"temperature\", display_name=\"Temperature\", value=0.1),\n        IntInput(\n            name=\"seed\",\n            display_name=\"Seed\",\n            info=\"The seed controls the reproducibility of the job.\",\n            advanced=True,\n            value=1,\n        ),\n    ]\n\n    def build_model(self) -> LanguageModel:  # type: ignore[type-var]\n        # self.output_schema is a list of dictionaries\n        # let's convert it to a dictionary\n        output_schema_dict: dict[str, str] = reduce(operator.ior, self.output_schema or {}, {})\n        openai_api_key = self.api_key\n        temperature = self.temperature\n        model_name: str = self.model_name\n        max_tokens = self.max_tokens\n        model_kwargs = self.model_kwargs or {}\n        openai_api_base = self.openai_api_base or \"https://api.openai.com/v1\"\n        json_mode = bool(output_schema_dict) or self.json_mode\n        seed = self.seed\n\n        if openai_api_key:\n            api_key = SecretStr(openai_api_key)\n        else:\n            api_key = None\n        output = ChatOpenAI(\n            max_tokens=max_tokens or None,\n            model_kwargs=model_kwargs,\n            model=model_name,\n            base_url=openai_api_base,\n            api_key=api_key,\n            temperature=temperature if temperature is not None else 0.1,\n            seed=seed,\n        )\n        if json_mode:\n            if output_schema_dict:\n                output = output.with_structured_output(schema=output_schema_dict, method=\"json_mode\")  # type: ignore\n            else:\n                output = output.bind(response_format={\"type\": \"json_object\"})  # type: ignore\n\n        return output  # type: ignore\n\n    def _get_exception_message(self, e: Exception):\n        \"\"\"\n        Get a message from an OpenAI exception.\n\n        Args:\n            exception (Exception): The exception to get the message from.\n\n        Returns:\n            str: The message from the exception.\n        \"\"\"\n\n        try:\n            from openai import BadRequestError\n        except ImportError:\n            return\n        if isinstance(e, BadRequestError):\n            message = e.body.get(\"message\")  # type: ignore\n            if message:\n                return message\n        return\n"
                                            },
                                            "input_value": {
                                                "advanced": False,
                                                "display_name": "Input",
                                                "dynamic": False,
                                                "info": "",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "input_value",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "json_mode": {
                                                "advanced": True,
                                                "display_name": "JSON Mode",
                                                "dynamic": False,
                                                "info": "If True, it will output JSON regardless of passing a schema.",
                                                "list": False,
                                                "name": "json_mode",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "bool",
                                                "value": False
                                            },
                                            "max_tokens": {
                                                "advanced": True,
                                                "display_name": "Max Tokens",
                                                "dynamic": False,
                                                "info": "The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
                                                "list": False,
                                                "name": "max_tokens",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "int",
                                                "value": ""
                                            },
                                            "model_kwargs": {
                                                "advanced": True,
                                                "display_name": "Model Kwargs",
                                                "dynamic": False,
                                                "info": "",
                                                "list": False,
                                                "name": "model_kwargs",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "type": "dict",
                                                "value": {}
                                            },
                                            "model_name": {
                                                "advanced": False,
                                                "display_name": "Model Name",
                                                "dynamic": False,
                                                "info": "",
                                                "load_from_db": False,
                                                "name": "model_name",
                                                "options": [
                                                    "gpt-4o-mini",
                                                    "gpt-4o",
                                                    "gpt-4-turbo",
                                                    "gpt-4-turbo-preview",
                                                    "gpt-4",
                                                    "gpt-3.5-turbo",
                                                    "gpt-3.5-turbo-0125"
                                                ],
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": "gpt-4o"
                                            },
                                            "openai_api_base": {
                                                "advanced": True,
                                                "display_name": "OpenAI API Base",
                                                "dynamic": False,
                                                "info": "The base URL of the OpenAI API. Defaults to https://api.openai.com/v1. You can change this to use other APIs like JinaChat, LocalAI and Prem.",
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "openai_api_base",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "output_schema": {
                                                "advanced": True,
                                                "display_name": "Schema",
                                                "dynamic": False,
                                                "info": "The schema for the Output of the model. You must pass the word JSON in the prompt. If left blank, JSON mode will be disabled.",
                                                "list": True,
                                                "name": "output_schema",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "type": "dict",
                                                "value": {}
                                            },
                                            "seed": {
                                                "advanced": True,
                                                "display_name": "Seed",
                                                "dynamic": False,
                                                "info": "The seed controls the reproducibility of the job.",
                                                "list": False,
                                                "name": "seed",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "int",
                                                "value": 1
                                            },
                                            "stream": {
                                                "advanced": True,
                                                "display_name": "Stream",
                                                "dynamic": False,
                                                "info": "Stream the response from the model. Streaming works only in Chat.",
                                                "list": False,
                                                "name": "stream",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "bool",
                                                "value": False
                                            },
                                            "system_message": {
                                                "advanced": True,
                                                "display_name": "System Message",
                                                "dynamic": False,
                                                "info": "System message to pass to the model.",
                                                "input_types": [
                                                    "Message"
                                                ],
                                                "list": False,
                                                "load_from_db": False,
                                                "name": "system_message",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_input": True,
                                                "trace_as_metadata": True,
                                                "type": "str",
                                                "value": ""
                                            },
                                            "temperature": {
                                                "advanced": False,
                                                "display_name": "Temperature",
                                                "dynamic": False,
                                                "info": "",
                                                "list": False,
                                                "name": "temperature",
                                                "placeholder": "",
                                                "required": False,
                                                "show": True,
                                                "title_case": False,
                                                "trace_as_metadata": True,
                                                "type": "float",
                                                "value": 0.1
                                            }
                                        }
                                    },
                                    "type": "OpenAIModel"
                                },
                                "dragging": False,
                                "height": 605,
                                "id": "OpenAIModel-ExXPZ",
                                "position": {
                                    "x": 3138.7638747868177,
                                    "y": 413.0859233500825
                                },
                                "positionAbsolute": {
                                    "x": 3138.7638747868177,
                                    "y": 413.0859233500825
                                },
                                "selected": False,
                                "type": "genericNode",
                                "width": 384
                            }
                        ],
                        "viewport": {
                            "x": -439.4891000981311,
                            "y": -36.825136403696206,
                            "zoom": 0.7131428627969274
                        }
                    },
                    "description": "Visit https://docs.langflow.org/tutorials/rag-with-astradb for a detailed guide of this project.\nThis project give you both Ingestion and RAG in a single file. You'll need to visit https://astra.datastax.com/ to create an Astra DB instance, your Token and grab an API Endpoint.\nRunning this project requires you to add a file in the Files component, then define a Collection Name and click on the Play icon on the Astra DB component. \n\nAfter the ingestion ends you are ready to click on the Run button at the lower left corner and start asking questions about your data.",
                    "endpoint_name": None,
                    "id": "11244a74-eba2-4b1f-b34a-2ce3ba421e2a",
                    "is_component": False,
                    "last_tested_version": "1.0.17",
                    "name": "Vector Store RAG"
                }
            ]
        }


class FlowgenTool(ToolInterface):
    def __init__(self):
        pass

    def call(self, flow: GraphDataModel):
        #TODO: validate that this flow is legit

        return {'output': flow, 'tool': self.__class__.__name__}
