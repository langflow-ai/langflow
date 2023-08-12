export const SAMPLE_ONE = {"name":"Simple Database Example","description":"This example allows you to query and ask questions about the database data.","data":{"nodes":[{"width":384,"height":273,"id":"SQLDatabase-ctJfl","type":"genericNode","position":{"x":332.0721978807386,"y":659.8076510596305},"data":{"type":"SQLDatabase","node":{"template":{"database_uri":{"required":true,"placeholder":"","show":true,"multiline":false,"password":false,"name":"database_uri","advanced":false,"info":"","type":"str","list":false,"value":"sqlite:///./langflow.db"},"engine_args":{"required":false,"placeholder":"","show":false,"multiline":false,"password":false,"name":"engine_args","advanced":false,"info":"","type":"code","list":false},"_type":"SQLDatabase"},"description":"Construct a SQLAlchemy engine from URI.","base_classes":["SQLDatabase","function"],"display_name":"SQLDatabase","custom_fields":{},"output_types":[],"documentation":""},"id":"SQLDatabase-ctJfl","value":null},"selected":false,"positionAbsolute":{"x":332.0721978807386,"y":659.8076510596305},"dragging":false},{"width":384,"height":287,"id":"SQLDatabaseChain-h0P6g","type":"genericNode","position":{"x":896,"y":644.84375},"data":{"type":"SQLDatabaseChain","node":{"template":{"db":{"required":true,"placeholder":"","show":true,"multiline":false,"password":false,"name":"db","advanced":false,"info":"","type":"SQLDatabase","list":false},"llm":{"required":true,"placeholder":"","show":true,"multiline":false,"password":false,"name":"llm","advanced":false,"info":"","type":"BaseLanguageModel","list":false},"prompt":{"required":true,"placeholder":"","show":true,"multiline":false,"password":false,"name":"prompt","advanced":false,"info":"","type":"BasePromptTemplate","list":false},"_type":"SQLDatabaseChain"},"description":"","base_classes":["SQLDatabaseChain","Chain","function"],"display_name":"SQLDatabaseChain","custom_fields":{},"output_types":[],"documentation":""},"id":"SQLDatabaseChain-h0P6g","value":null},"selected":false,"dragging":false,"positionAbsolute":{"x":896,"y":644.84375}},{"width":384,"height":641,"id":"ChatOpenAI-599FM","type":"genericNode","position":{"x":318,"y":1000.84375},"data":{"type":"ChatOpenAI","node":{"template":{"callbacks":{"required":false,"placeholder":"","show":false,"multiline":false,"password":false,"name":"callbacks","advanced":false,"info":"","type":"langchain.callbacks.base.BaseCallbackHandler","list":true},"cache":{"required":false,"placeholder":"","show":false,"multiline":false,"password":false,"name":"cache","advanced":false,"info":"","type":"bool","list":false},"client":{"required":false,"placeholder":"","show":false,"multiline":false,"password":false,"name":"client","advanced":false,"info":"","type":"Any","list":false},"max_retries":{"required":false,"placeholder":"","show":false,"multiline":false,"value":6,"password":false,"name":"max_retries","advanced":false,"info":"","type":"int","list":false},"max_tokens":{"required":false,"placeholder":"","show":true,"multiline":false,"password":true,"name":"max_tokens","advanced":false,"info":"","type":"int","list":false,"value":""},"model_kwargs":{"required":false,"placeholder":"","show":true,"multiline":false,"password":false,"name":"model_kwargs","advanced":true,"info":"","type":"code","list":false},"model_name":{"required":false,"placeholder":"","show":true,"multiline":false,"value":"gpt-3.5-turbo-0613","password":false,"options":["gpt-3.5-turbo-0613","gpt-3.5-turbo","gpt-3.5-turbo-16k-0613","gpt-3.5-turbo-16k","gpt-4-0613","gpt-4-32k-0613","gpt-4","gpt-4-32k"],"name":"model_name","advanced":false,"info":"","type":"str","list":true},"n":{"required":false,"placeholder":"","show":false,"multiline":false,"value":1,"password":false,"name":"n","advanced":false,"info":"","type":"int","list":false},"openai_api_base":{"required":false,"placeholder":"","show":true,"multiline":false,"password":false,"name":"openai_api_base","display_name":"OpenAI API Base","advanced":false,"info":"\nThe base URL of the OpenAI API. Defaults to https://api.openai.com/v1.\n\nYou can change this to use other APIs like JinaChat, LocalAI and Prem.\n","type":"str","list":false},"openai_api_key":{"required":false,"placeholder":"","show":true,"multiline":false,"value":"","password":true,"name":"openai_api_key","display_name":"OpenAI API Key","advanced":false,"info":"","type":"str","list":false},"openai_organization":{"required":false,"placeholder":"","show":false,"multiline":false,"password":false,"name":"openai_organization","display_name":"OpenAI Organization","advanced":false,"info":"","type":"str","list":false},"openai_proxy":{"required":false,"placeholder":"","show":false,"multiline":false,"password":false,"name":"openai_proxy","display_name":"OpenAI Proxy","advanced":false,"info":"","type":"str","list":false},"request_timeout":{"required":false,"placeholder":"","show":false,"multiline":false,"password":false,"name":"request_timeout","advanced":false,"info":"","type":"float","list":false},"streaming":{"required":false,"placeholder":"","show":false,"multiline":false,"value":false,"password":false,"name":"streaming","advanced":false,"info":"","type":"bool","list":false},"tags":{"required":false,"placeholder":"","show":false,"multiline":false,"password":false,"name":"tags","advanced":false,"info":"","type":"str","list":true},"temperature":{"required":false,"placeholder":"","show":true,"multiline":false,"value":0.7,"password":false,"name":"temperature","advanced":false,"info":"","type":"float","list":false},"tiktoken_model_name":{"required":false,"placeholder":"","show":false,"multiline":false,"password":false,"name":"tiktoken_model_name","advanced":false,"info":"","type":"str","list":false},"verbose":{"required":false,"placeholder":"","show":false,"multiline":false,"value":false,"password":false,"name":"verbose","advanced":false,"info":"","type":"bool","list":false},"_type":"ChatOpenAI"},"description":"Wrapper around OpenAI Chat large language models.","base_classes":["BaseChatModel","BaseLanguageModel","ChatOpenAI","BaseLLM"],"display_name":"ChatOpenAI","custom_fields":{},"output_types":[],"documentation":"https://python.langchain.com/docs/modules/model_io/models/chat/integrations/openai"},"id":"ChatOpenAI-599FM","value":null},"selected":false,"positionAbsolute":{"x":318,"y":1000.84375},"dragging":false},{"width":384,"height":531,"id":"PromptTemplate-l1ltb","type":"genericNode","position":{"x":322,"y":92.84375},"data":{"type":"PromptTemplate","node":{"template":{"output_parser":{"required":false,"placeholder":"","show":false,"multiline":false,"password":false,"name":"output_parser","advanced":false,"info":"","type":"BaseOutputParser","list":false},"input_variables":{"required":true,"placeholder":"","show":false,"multiline":false,"password":false,"name":"input_variables","advanced":false,"info":"","type":"str","list":true,"value":["dialect","table_info","input"]},"partial_variables":{"required":false,"placeholder":"","show":false,"multiline":false,"password":false,"name":"partial_variables","advanced":false,"info":"","type":"code","list":false},"template":{"required":true,"placeholder":"","show":true,"multiline":true,"password":false,"name":"template","advanced":false,"info":"","type":"prompt","list":false,"value":"Given an input question, first create a syntactically correct {dialect} query to run, then look at the results of the query and return the answer.\nUse the following format:\n\nQuestion: \"Question here\"\nSQLQuery: \"SQL Query to run\"\nSQLResult: \"Result of the SQLQuery\"\nAnswer: \"Final answer here\"\n\nOnly use the following tables:\n\n{table_info}\n\nIf someone asks for the table foobar, they really mean the employee table.\n\nQuestion: {input}"},"template_format":{"required":false,"placeholder":"","show":false,"multiline":false,"value":"f-string","password":false,"name":"template_format","advanced":false,"info":"","type":"str","list":false},"validate_template":{"required":false,"placeholder":"","show":false,"multiline":false,"value":true,"password":false,"name":"validate_template","advanced":false,"info":"","type":"bool","list":false},"_type":"PromptTemplate","dialect":{"required":false,"placeholder":"","show":true,"multiline":true,"value":"","password":false,"name":"dialect","display_name":"dialect","advanced":false,"input_types":["Document","BaseOutputParser"],"info":"","type":"str","list":false},"table_info":{"required":false,"placeholder":"","show":true,"multiline":true,"value":"","password":false,"name":"table_info","display_name":"table_info","advanced":false,"input_types":["Document","BaseOutputParser"],"info":"","type":"str","list":false},"input":{"required":false,"placeholder":"","show":true,"multiline":true,"value":"","password":false,"name":"input","display_name":"input","advanced":false,"input_types":["Document","BaseOutputParser"],"info":"","type":"str","list":false}},"description":"Schema to represent a prompt for an LLM.","base_classes":["StringPromptTemplate","BasePromptTemplate","PromptTemplate"],"name":"","display_name":"PromptTemplate","documentation":"https://python.langchain.com/docs/modules/model_io/prompts/prompt_templates/","custom_fields":{"":["dialect","table_info","input"],"template":["dialect","table_info","input"]},"output_types":[],"field_formatters":{"formatters":{"openai_api_key":{}},"base_formatters":{"kwargs":{},"optional":{},"list":{},"dict":{},"union":{},"multiline":{},"show":{},"password":{},"default":{},"headers":{},"dict_code_file":{},"model_fields":{"MODEL_DICT":{"OpenAI":["text-davinci-003","text-davinci-002","text-curie-001","text-babbage-001","text-ada-001"],"ChatOpenAI":["gpt-3.5-turbo-0613","gpt-3.5-turbo","gpt-3.5-turbo-16k-0613","gpt-3.5-turbo-16k","gpt-4-0613","gpt-4-32k-0613","gpt-4","gpt-4-32k"],"Anthropic":["claude-v1","claude-v1-100k","claude-instant-v1","claude-instant-v1-100k","claude-v1.3","claude-v1.3-100k","claude-v1.2","claude-v1.0","claude-instant-v1.1","claude-instant-v1.1-100k","claude-instant-v1.0"],"ChatAnthropic":["claude-v1","claude-v1-100k","claude-instant-v1","claude-instant-v1-100k","claude-v1.3","claude-v1.3-100k","claude-v1.2","claude-v1.0","claude-instant-v1.1","claude-instant-v1.1-100k","claude-instant-v1.0"]}}}}},"id":"PromptTemplate-l1ltb","value":null},"selected":false,"positionAbsolute":{"x":322,"y":92.84375},"dragging":false}],"edges":[{"source":"SQLDatabase-ctJfl","sourceHandle":"SQLDatabase|SQLDatabase-ctJfl|SQLDatabase|function","target":"SQLDatabaseChain-h0P6g","targetHandle":"SQLDatabase|db|SQLDatabaseChain-h0P6g","style":{"stroke":"#555555"},"className":"","animated":false,"id":"reactflow__edge-SQLDatabase-ctJflSQLDatabase|SQLDatabase-ctJfl|SQLDatabase|function-SQLDatabaseChain-h0P6gSQLDatabase|db|SQLDatabaseChain-h0P6g","selected":false},{"source":"ChatOpenAI-599FM","sourceHandle":"ChatOpenAI|ChatOpenAI-599FM|BaseChatModel|BaseLanguageModel|ChatOpenAI|BaseLLM","target":"SQLDatabaseChain-h0P6g","targetHandle":"BaseLanguageModel|llm|SQLDatabaseChain-h0P6g","style":{"stroke":"#555555"},"className":"","animated":false,"id":"reactflow__edge-ChatOpenAI-599FMChatOpenAI|ChatOpenAI-599FM|BaseChatModel|ChatOpenAI|BaseLanguageModel|BaseLLM-SQLDatabaseChain-h0P6gBaseLanguageModel|llm|SQLDatabaseChain-h0P6g","selected":false},{"source":"PromptTemplate-l1ltb","sourceHandle":"PromptTemplate|PromptTemplate-l1ltb|StringPromptTemplate|BasePromptTemplate|PromptTemplate","target":"SQLDatabaseChain-h0P6g","targetHandle":"BasePromptTemplate|prompt|SQLDatabaseChain-h0P6g","style":{"stroke":"#555555"},"className":"","animated":false,"id":"reactflow__edge-PromptTemplate-l1ltbPromptTemplate|PromptTemplate-l1ltb|PromptTemplate|BasePromptTemplate|StringPromptTemplate-SQLDatabaseChain-h0P6gBasePromptTemplate|prompt|SQLDatabaseChain-h0P6g","selected":false}],"viewport":{"x":158.0414930453665,"y":-7.57084482657433,"zoom":0.4918128998180644}},"id":"a094a691-2c75-4945-9d9c-2bfe69f4093b","style":null}
export const SAMPLE_TWO = {
    "description": "Load a PDF and start asking questions about it.",
    "name": "PDF Loader",
    "data": {
        "nodes": [
            {
                "width": 384,
                "height": 267,
                "id": "VectorStoreAgent-lrDhT",
                "type": "genericNode",
                "position": {
                    "x": 1759.0521504033006,
                    "y": -1084.8109307754983
                },
                "data": {
                    "type": "VectorStoreAgent",
                    "node": {
                        "template": {
                            "llm": {
                                "required": true,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "password": false,
                                "name": "llm",
                                "display_name": "LLM",
                                "advanced": false,
                                "info": "",
                                "type": "BaseLanguageModel",
                                "list": false
                            },
                            "vectorstoreinfo": {
                                "required": true,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "password": false,
                                "name": "vectorstoreinfo",
                                "display_name": "Vector Store Info",
                                "advanced": false,
                                "info": "",
                                "type": "VectorStoreInfo",
                                "list": false
                            },
                            "_type": "vectorstore_agent"
                        },
                        "description": "Construct an agent from a Vector Store.",
                        "base_classes": [
                            "AgentExecutor"
                        ],
                        "display_name": "VectorStoreAgent",
                        "documentation": ""
                    },
                    "id": "VectorStoreAgent-lrDhT",
                    "value": null
                },
                "selected": false,
                "positionAbsolute": {
                    "x": 1759.0521504033006,
                    "y": -1084.8109307754983
                }
            },
            {
                "width": 384,
                "height": 399,
                "id": "VectorStoreInfo-MPfyi",
                "type": "genericNode",
                "position": {
                    "x": 1196.8213224104938,
                    "y": -1126.393770900602
                },
                "data": {
                    "type": "VectorStoreInfo",
                    "node": {
                        "template": {
                            "vectorstore": {
                                "required": true,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "password": false,
                                "name": "vectorstore",
                                "advanced": false,
                                "info": "",
                                "type": "VectorStore",
                                "list": false
                            },
                            "description": {
                                "required": true,
                                "placeholder": "",
                                "show": true,
                                "multiline": true,
                                "password": false,
                                "name": "description",
                                "advanced": false,
                                "info": "",
                                "type": "str",
                                "list": false,
                                "value": "Information about a PDF File"
                            },
                            "name": {
                                "required": true,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "password": false,
                                "name": "name",
                                "advanced": false,
                                "info": "",
                                "type": "str",
                                "list": false,
                                "value": "PDF"
                            },
                            "_type": "VectorStoreInfo"
                        },
                        "description": "Information about a vectorstore.",
                        "base_classes": [
                            "VectorStoreInfo"
                        ],
                        "display_name": "VectorStoreInfo",
                        "documentation": ""
                    },
                    "id": "VectorStoreInfo-MPfyi",
                    "value": null
                },
                "selected": false,
                "positionAbsolute": {
                    "x": 1196.8213224104938,
                    "y": -1126.393770900602
                },
                "dragging": false
            },
            {
                "width": 384,
                "height": 359,
                "id": "OpenAIEmbeddings-rzKno",
                "type": "genericNode",
                "position": {
                    "x": 320.8037105955719,
                    "y": -541.6464393473227
                },
                "data": {
                    "type": "OpenAIEmbeddings",
                    "node": {
                        "template": {
                            "allowed_special": {
                                "required": false,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "value": [],
                                "password": false,
                                "name": "allowed_special",
                                "advanced": true,
                                "info": "",
                                "type": "Literal'all'",
                                "list": true
                            },
                            "disallowed_special": {
                                "required": false,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "value": "all",
                                "password": false,
                                "name": "disallowed_special",
                                "advanced": true,
                                "info": "",
                                "type": "Literal'all'",
                                "list": true
                            },
                            "chunk_size": {
                                "required": false,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "value": 1000,
                                "password": false,
                                "name": "chunk_size",
                                "advanced": true,
                                "info": "",
                                "type": "int",
                                "list": false
                            },
                            "client": {
                                "required": false,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "password": false,
                                "name": "client",
                                "advanced": true,
                                "info": "",
                                "type": "Any",
                                "list": false
                            },
                            "deployment": {
                                "required": false,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "value": "text-embedding-ada-002",
                                "password": false,
                                "name": "deployment",
                                "advanced": true,
                                "info": "",
                                "type": "str",
                                "list": false
                            },
                            "embedding_ctx_length": {
                                "required": false,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "value": 8191,
                                "password": false,
                                "name": "embedding_ctx_length",
                                "advanced": true,
                                "info": "",
                                "type": "int",
                                "list": false
                            },
                            "headers": {
                                "required": false,
                                "placeholder": "",
                                "show": false,
                                "multiline": true,
                                "value": "{'Authorization':\n            'Bearer <token>'}",
                                "password": false,
                                "name": "headers",
                                "advanced": true,
                                "info": "",
                                "type": "Any",
                                "list": false
                            },
                            "max_retries": {
                                "required": false,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "value": 6,
                                "password": false,
                                "name": "max_retries",
                                "advanced": true,
                                "info": "",
                                "type": "int",
                                "list": false
                            },
                            "model": {
                                "required": false,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "value": "text-embedding-ada-002",
                                "password": false,
                                "name": "model",
                                "advanced": true,
                                "info": "",
                                "type": "str",
                                "list": false
                            },
                            "openai_api_base": {
                                "required": false,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "password": true,
                                "name": "openai_api_base",
                                "display_name": "OpenAI API Base",
                                "advanced": true,
                                "info": "",
                                "type": "str",
                                "list": false,
                                "value": ""
                            },
                            "openai_api_key": {
                                "required": false,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "value": "",
                                "password": true,
                                "name": "openai_api_key",
                                "display_name": "OpenAI API Key",
                                "advanced": false,
                                "info": "",
                                "type": "str",
                                "list": false
                            },
                            "openai_api_type": {
                                "required": false,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "password": true,
                                "name": "openai_api_type",
                                "display_name": "OpenAI API Type",
                                "advanced": true,
                                "info": "",
                                "type": "str",
                                "list": false,
                                "value": ""
                            },
                            "openai_api_version": {
                                "required": false,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "password": true,
                                "name": "openai_api_version",
                                "display_name": "OpenAI API Version",
                                "advanced": true,
                                "info": "",
                                "type": "str",
                                "list": false,
                                "value": ""
                            },
                            "openai_organization": {
                                "required": false,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "password": false,
                                "name": "openai_organization",
                                "display_name": "OpenAI Organization",
                                "advanced": true,
                                "info": "",
                                "type": "str",
                                "list": false
                            },
                            "openai_proxy": {
                                "required": false,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "password": false,
                                "name": "openai_proxy",
                                "display_name": "OpenAI Proxy",
                                "advanced": true,
                                "info": "",
                                "type": "str",
                                "list": false
                            },
                            "request_timeout": {
                                "required": false,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "password": false,
                                "name": "request_timeout",
                                "advanced": true,
                                "info": "",
                                "type": "float",
                                "list": false
                            },
                            "tiktoken_model_name": {
                                "required": false,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "password": true,
                                "name": "tiktoken_model_name",
                                "advanced": false,
                                "info": "",
                                "type": "str",
                                "list": false,
                                "value": ""
                            },
                            "_type": "OpenAIEmbeddings"
                        },
                        "description": "Wrapper around OpenAI embedding models.",
                        "base_classes": [
                            "Embeddings",
                            "OpenAIEmbeddings"
                        ],
                        "display_name": "OpenAIEmbeddings",
                        "documentation": "https://python.langchain.com/docs/modules/data_connection/text_embedding/integrations/openai"
                    },
                    "id": "OpenAIEmbeddings-rzKno",
                    "value": null
                },
                "selected": false,
                "positionAbsolute": {
                    "x": 320.8037105955719,
                    "y": -541.6464393473227
                }
            },
            {
                "width": 384,
                "height": 515,
                "id": "Chroma-VwlqF",
                "type": "genericNode",
                "position": {
                    "x": 781.6596570821403,
                    "y": -1096.3341720971546
                },
                "data": {
                    "type": "Chroma",
                    "node": {
                        "template": {
                            "client": {
                                "required": false,
                                "placeholder": "",
                                "show": false,
                                "multiline": false,
                                "password": false,
                                "name": "client",
                                "advanced": false,
                                "info": "",
                                "type": "chromadb.Client",
                                "list": false
                            },
                            "client_settings": {
                                "required": false,
                                "placeholder": "",
                                "show": false,
                                "multiline": false,
                                "password": false,
                                "name": "client_settings",
                                "advanced": false,
                                "info": "",
                                "type": "chromadb.config.Setting",
                                "list": true
                            },
                            "documents": {
                                "required": false,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "password": false,
                                "name": "documents",
                                "display_name": "Documents",
                                "advanced": false,
                                "info": "",
                                "type": "Document",
                                "list": true
                            },
                            "embedding": {
                                "required": true,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "password": false,
                                "name": "embedding",
                                "display_name": "Embedding",
                                "advanced": false,
                                "info": "",
                                "type": "Embeddings",
                                "list": false
                            },
                            "collection_name": {
                                "required": false,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "value": "langflow",
                                "password": false,
                                "name": "collection_name",
                                "advanced": false,
                                "info": "",
                                "type": "str",
                                "list": false
                            },
                            "ids": {
                                "required": false,
                                "placeholder": "",
                                "show": false,
                                "multiline": false,
                                "password": false,
                                "name": "ids",
                                "advanced": false,
                                "info": "",
                                "type": "str",
                                "list": true
                            },
                            "metadatas": {
                                "required": false,
                                "placeholder": "",
                                "show": false,
                                "multiline": false,
                                "password": false,
                                "name": "metadatas",
                                "advanced": false,
                                "info": "",
                                "type": "code",
                                "list": true
                            },
                            "persist": {
                                "required": false,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "value": false,
                                "password": false,
                                "name": "persist",
                                "display_name": "Persist",
                                "advanced": false,
                                "info": "",
                                "type": "bool",
                                "list": false
                            },
                            "persist_directory": {
                                "required": false,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "password": false,
                                "name": "persist_directory",
                                "advanced": false,
                                "info": "",
                                "type": "str",
                                "list": false
                            },
                            "search_kwargs": {
                                "required": false,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "value": "{}",
                                "password": false,
                                "name": "search_kwargs",
                                "advanced": true,
                                "info": "",
                                "type": "code",
                                "list": false
                            },
                            "_type": "Chroma"
                        },
                        "description": "Create a Chroma vectorstore from a raw documents.",
                        "base_classes": [
                            "Chroma",
                            "VectorStore",
                            "BaseRetriever",
                            "VectorStoreRetriever"
                        ],
                        "display_name": "Chroma",
                        "custom_fields": {},
                        "output_types": [],
                        "documentation": "https://python.langchain.com/docs/modules/data_connection/vectorstores/integrations/chroma"
                    },
                    "id": "Chroma-VwlqF",
                    "value": null
                },
                "selected": false,
                "positionAbsolute": {
                    "x": 781.6596570821403,
                    "y": -1096.3341720971546
                }
            },
            {
                "width": 384,
                "height": 595,
                "id": "RecursiveCharacterTextSplitter-Fc0Vx",
                "type": "genericNode",
                "position": {
                    "x": 250.91992861065756,
                    "y": -1150.9950743649817
                },
                "data": {
                    "type": "RecursiveCharacterTextSplitter",
                    "node": {
                        "template": {
                            "documents": {
                                "required": true,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "password": false,
                                "name": "documents",
                                "advanced": false,
                                "info": "",
                                "type": "Document",
                                "list": false
                            },
                            "chunk_overlap": {
                                "required": true,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "value": 200,
                                "password": false,
                                "name": "chunk_overlap",
                                "display_name": "Chunk Overlap",
                                "advanced": false,
                                "info": "",
                                "type": "int",
                                "list": false
                            },
                            "chunk_size": {
                                "required": true,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "value": 1000,
                                "password": false,
                                "name": "chunk_size",
                                "display_name": "Chunk Size",
                                "advanced": false,
                                "info": "",
                                "type": "int",
                                "list": false
                            },
                            "separator_type": {
                                "required": true,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "value": "Text",
                                "password": false,
                                "options": [
                                    "Text",
                                    "cpp",
                                    "go",
                                    "html",
                                    "java",
                                    "js",
                                    "latex",
                                    "markdown",
                                    "php",
                                    "proto",
                                    "python",
                                    "rst",
                                    "ruby",
                                    "rust",
                                    "scala",
                                    "sol",
                                    "swift"
                                ],
                                "name": "separator_type",
                                "display_name": "Separator Type",
                                "advanced": false,
                                "info": "",
                                "type": "str",
                                "list": true
                            },
                            "separators": {
                                "required": true,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "value": ".",
                                "password": false,
                                "name": "separators",
                                "display_name": "Separator",
                                "advanced": false,
                                "info": "",
                                "type": "str",
                                "list": false
                            },
                            "_type": "RecursiveCharacterTextSplitter"
                        },
                        "description": "Implementation of splitting text that looks at characters.",
                        "base_classes": [
                            "Document"
                        ],
                        "display_name": "RecursiveCharacterTextSplitter",
                        "custom_fields": {},
                        "output_types": [
                            "Document"
                        ],
                        "documentation": "https://python.langchain.com/docs/modules/data_connection/document_transformers/text_splitters/recursive_text_splitter"
                    },
                    "id": "RecursiveCharacterTextSplitter-Fc0Vx",
                    "value": null
                },
                "selected": false,
                "positionAbsolute": {
                    "x": 250.91992861065756,
                    "y": -1150.9950743649817
                }
            },
            {
                "width": 384,
                "height": 641,
                "id": "ChatOpenAI-q9GAF",
                "type": "genericNode",
                "position": {
                    "x": 1201.3143261061039,
                    "y": -704.8915816630376
                },
                "data": {
                    "type": "ChatOpenAI",
                    "node": {
                        "template": {
                            "callbacks": {
                                "required": false,
                                "placeholder": "",
                                "show": false,
                                "multiline": false,
                                "password": false,
                                "name": "callbacks",
                                "advanced": false,
                                "info": "",
                                "type": "langchain.callbacks.base.BaseCallbackHandler",
                                "list": true
                            },
                            "cache": {
                                "required": false,
                                "placeholder": "",
                                "show": false,
                                "multiline": false,
                                "password": false,
                                "name": "cache",
                                "advanced": false,
                                "info": "",
                                "type": "bool",
                                "list": false
                            },
                            "client": {
                                "required": false,
                                "placeholder": "",
                                "show": false,
                                "multiline": false,
                                "password": false,
                                "name": "client",
                                "advanced": false,
                                "info": "",
                                "type": "Any",
                                "list": false
                            },
                            "max_retries": {
                                "required": false,
                                "placeholder": "",
                                "show": false,
                                "multiline": false,
                                "value": 6,
                                "password": false,
                                "name": "max_retries",
                                "advanced": false,
                                "info": "",
                                "type": "int",
                                "list": false
                            },
                            "max_tokens": {
                                "required": false,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "password": true,
                                "name": "max_tokens",
                                "advanced": false,
                                "info": "",
                                "type": "int",
                                "list": false,
                                "value": ""
                            },
                            "model_kwargs": {
                                "required": false,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "password": false,
                                "name": "model_kwargs",
                                "advanced": true,
                                "info": "",
                                "type": "code",
                                "list": false
                            },
                            "model_name": {
                                "required": false,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "value": "gpt-3.5-turbo-0613",
                                "password": false,
                                "options": [
                                    "gpt-3.5-turbo-0613",
                                    "gpt-3.5-turbo",
                                    "gpt-3.5-turbo-16k-0613",
                                    "gpt-3.5-turbo-16k",
                                    "gpt-4-0613",
                                    "gpt-4-32k-0613",
                                    "gpt-4",
                                    "gpt-4-32k"
                                ],
                                "name": "model_name",
                                "advanced": false,
                                "info": "",
                                "type": "str",
                                "list": true
                            },
                            "n": {
                                "required": false,
                                "placeholder": "",
                                "show": false,
                                "multiline": false,
                                "value": 1,
                                "password": false,
                                "name": "n",
                                "advanced": false,
                                "info": "",
                                "type": "int",
                                "list": false
                            },
                            "openai_api_base": {
                                "required": false,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "password": false,
                                "name": "openai_api_base",
                                "display_name": "OpenAI API Base",
                                "advanced": false,
                                "info": "\nThe base URL of the OpenAI API. Defaults to https://api.openai.com/v1.\n\nYou can change this to use other APIs like JinaChat, LocalAI and Prem.\n",
                                "type": "str",
                                "list": false
                            },
                            "openai_api_key": {
                                "required": false,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "value": "",
                                "password": true,
                                "name": "openai_api_key",
                                "display_name": "OpenAI API Key",
                                "advanced": false,
                                "info": "",
                                "type": "str",
                                "list": false
                            },
                            "openai_organization": {
                                "required": false,
                                "placeholder": "",
                                "show": false,
                                "multiline": false,
                                "password": false,
                                "name": "openai_organization",
                                "display_name": "OpenAI Organization",
                                "advanced": false,
                                "info": "",
                                "type": "str",
                                "list": false
                            },
                            "openai_proxy": {
                                "required": false,
                                "placeholder": "",
                                "show": false,
                                "multiline": false,
                                "password": false,
                                "name": "openai_proxy",
                                "display_name": "OpenAI Proxy",
                                "advanced": false,
                                "info": "",
                                "type": "str",
                                "list": false
                            },
                            "request_timeout": {
                                "required": false,
                                "placeholder": "",
                                "show": false,
                                "multiline": false,
                                "password": false,
                                "name": "request_timeout",
                                "advanced": false,
                                "info": "",
                                "type": "float",
                                "list": false
                            },
                            "streaming": {
                                "required": false,
                                "placeholder": "",
                                "show": false,
                                "multiline": false,
                                "value": false,
                                "password": false,
                                "name": "streaming",
                                "advanced": false,
                                "info": "",
                                "type": "bool",
                                "list": false
                            },
                            "tags": {
                                "required": false,
                                "placeholder": "",
                                "show": false,
                                "multiline": false,
                                "password": false,
                                "name": "tags",
                                "advanced": false,
                                "info": "",
                                "type": "str",
                                "list": true
                            },
                            "temperature": {
                                "required": false,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "value": "0.2",
                                "password": false,
                                "name": "temperature",
                                "advanced": false,
                                "info": "",
                                "type": "float",
                                "list": false
                            },
                            "tiktoken_model_name": {
                                "required": false,
                                "placeholder": "",
                                "show": false,
                                "multiline": false,
                                "password": false,
                                "name": "tiktoken_model_name",
                                "advanced": false,
                                "info": "",
                                "type": "str",
                                "list": false
                            },
                            "verbose": {
                                "required": false,
                                "placeholder": "",
                                "show": false,
                                "multiline": false,
                                "value": false,
                                "password": false,
                                "name": "verbose",
                                "advanced": false,
                                "info": "",
                                "type": "bool",
                                "list": false
                            },
                            "_type": "ChatOpenAI"
                        },
                        "description": "Wrapper around OpenAI Chat large language models.",
                        "base_classes": [
                            "BaseChatModel",
                            "ChatOpenAI",
                            "BaseLanguageModel",
                            "BaseLLM"
                        ],
                        "display_name": "ChatOpenAI",
                        "custom_fields": {},
                        "output_types": [],
                        "documentation": "https://python.langchain.com/docs/modules/model_io/models/chat/integrations/openai"
                    },
                    "id": "ChatOpenAI-q9GAF",
                    "value": null
                },
                "selected": false,
                "positionAbsolute": {
                    "x": 1201.3143261061039,
                    "y": -704.8915816630376
                }
            },
            {
                "width": 384,
                "height": 379,
                "id": "PyPDFLoader-ryD3L",
                "type": "genericNode",
                "position": {
                    "x": -249.89545919397153,
                    "y": -1327.2789565489504
                },
                "data": {
                    "type": "PyPDFLoader",
                    "node": {
                        "template": {
                            "file_path": {
                                "required": true,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "value": "",
                                "suffixes": [
                                    ".pdf"
                                ],
                                "fileTypes": [
                                    "pdf"
                                ],
                                "password": false,
                                "name": "file_path",
                                "advanced": false,
                                "info": "",
                                "type": "file",
                                "list": false,
                                "file_path": null
                            },
                            "metadata": {
                                "required": true,
                                "placeholder": "",
                                "show": true,
                                "multiline": false,
                                "value": "{}",
                                "password": false,
                                "name": "metadata",
                                "display_name": "Metadata",
                                "advanced": false,
                                "info": "",
                                "type": "code",
                                "list": false
                            },
                            "_type": "PyPDFLoader"
                        },
                        "description": "Loads a PDF with pypdf and chunks at character level.",
                        "base_classes": [
                            "Document"
                        ],
                        "display_name": "PyPDFLoader",
                        "custom_fields": {},
                        "output_types": [
                            "Document"
                        ],
                        "documentation": "https://python.langchain.com/docs/modules/data_connection/document_loaders/how_to/pdf"
                    },
                    "id": "PyPDFLoader-ryD3L",
                    "value": null
                },
                "selected": false,
                "positionAbsolute": {
                    "x": -249.89545919397153,
                    "y": -1327.2789565489504
                },
                "dragging": false
            }
        ],
        "edges": [
            {
                "source": "VectorStoreInfo-MPfyi",
                "target": "VectorStoreAgent-lrDhT",
                "sourceHandle": "VectorStoreInfo|VectorStoreInfo-MPfyi|VectorStoreInfo",
                "targetHandle": "VectorStoreInfo|vectorstoreinfo|VectorStoreAgent-lrDhT",
                "id": "reactflow__edge-VectorStoreInfo-MPfyiVectorStoreInfo|VectorStoreInfo-MPfyi|VectorStoreInfo-VectorStoreAgent-lrDhTVectorStoreInfo|vectorstoreinfo|VectorStoreAgent-lrDhT",
                "style": {
                    "stroke": "inherit"
                },
                "className": "stroke-gray-900 ",
                "animated": false,
                "selected": false
            },
            {
                "source": "Chroma-VwlqF",
                "target": "VectorStoreInfo-MPfyi",
                "sourceHandle": "Chroma|Chroma-VwlqF|Chroma|VectorStore|BaseRetriever|VectorStoreRetriever",
                "targetHandle": "VectorStore|vectorstore|VectorStoreInfo-MPfyi",
                "id": "reactflow__edge-Chroma-VwlqFChroma|Chroma-VwlqF|Chroma|VectorStore|BaseRetriever|VectorStoreRetriever-VectorStoreInfo-MPfyiVectorStore|vectorstore|VectorStoreInfo-MPfyi",
                "style": {
                    "stroke": "inherit"
                },
                "className": "stroke-gray-900 ",
                "animated": false,
                "selected": false
            },
            {
                "source": "RecursiveCharacterTextSplitter-Fc0Vx",
                "target": "Chroma-VwlqF",
                "sourceHandle": "RecursiveCharacterTextSplitter|RecursiveCharacterTextSplitter-Fc0Vx|Document",
                "targetHandle": "Document|documents|Chroma-VwlqF",
                "id": "reactflow__edge-RecursiveCharacterTextSplitter-Fc0VxRecursiveCharacterTextSplitter|RecursiveCharacterTextSplitter-Fc0Vx|Document-Chroma-VwlqFDocument|documents|Chroma-VwlqF",
                "style": {
                    "stroke": "inherit"
                },
                "className": "stroke-gray-900 ",
                "animated": false,
                "selected": false
            },
            {
                "source": "ChatOpenAI-q9GAF",
                "target": "VectorStoreAgent-lrDhT",
                "sourceHandle": "ChatOpenAI|ChatOpenAI-q9GAF|BaseChatModel|ChatOpenAI|BaseLanguageModel|BaseLLM",
                "targetHandle": "BaseLanguageModel|llm|VectorStoreAgent-lrDhT",
                "id": "reactflow__edge-ChatOpenAI-q9GAFChatOpenAI|ChatOpenAI-q9GAF|BaseChatModel|ChatOpenAI|BaseLanguageModel|BaseLLM-VectorStoreAgent-lrDhTBaseLanguageModel|llm|VectorStoreAgent-lrDhT",
                "style": {
                    "stroke": "inherit"
                },
                "className": "stroke-gray-900 ",
                "animated": false,
                "selected": false
            },
            {
                "source": "OpenAIEmbeddings-rzKno",
                "target": "Chroma-VwlqF",
                "sourceHandle": "OpenAIEmbeddings|OpenAIEmbeddings-rzKno|Embeddings|OpenAIEmbeddings",
                "targetHandle": "Embeddings|embedding|Chroma-VwlqF",
                "id": "reactflow__edge-OpenAIEmbeddings-rzKnoOpenAIEmbeddings|OpenAIEmbeddings-rzKno|Embeddings|OpenAIEmbeddings-Chroma-VwlqFEmbeddings|embedding|Chroma-VwlqF",
                "style": {
                    "stroke": "inherit"
                },
                "className": "stroke-gray-900 ",
                "animated": false,
                "selected": false
            },
            {
                "source": "PyPDFLoader-ryD3L",
                "sourceHandle": "PyPDFLoader|PyPDFLoader-ryD3L|Document",
                "target": "RecursiveCharacterTextSplitter-Fc0Vx",
                "targetHandle": "Document|documents|RecursiveCharacterTextSplitter-Fc0Vx",
                "style": {
                    "stroke": "inherit"
                },
                "className": "stroke-foreground ",
                "animated": false,
                "id": "reactflow__edge-PyPDFLoader-ryD3LPyPDFLoader|PyPDFLoader-ryD3L|Document-RecursiveCharacterTextSplitter-Fc0VxDocument|documents|RecursiveCharacterTextSplitter-Fc0Vx",
                "selected": false
            }
        ],
        "viewport": {
            "x": 166.94222792229124,
            "y": 855.0494041295599,
            "zoom": 0.4761180623450985
        }
    },
    "id": "d9d9969d-cd67-4839-a2fe-bf8e4aa2ac53"
}