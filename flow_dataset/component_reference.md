# Langflow Component Reference

All available components with their inputs and outputs.

## FAISS

### FAISS (`FAISS`)
FAISS Vector Store with search capabilities
- **Inputs**: `embedding` (Embeddings), `ingest_data` (Data/DataFrame), `search_query` (Message)
- **Outputs**: `search_results` (Data), `dataframe` (DataFrame)

## Notion

### Add Content to Page  (`AddContentToPage`)
Convert markdown text to Notion blocks and append them to a Notion page.
- **Inputs**: `markdown_text` (Message)
- **Outputs**: `api_run_model` (Data), `api_build_tool` (Tool)

### Create Page  (`NotionPageCreator`)
A component for creating Notion pages.
- **Inputs**: `properties_json` (Message)
- **Outputs**: `api_run_model` (Data), `api_build_tool` (Tool)

### List Database Properties  (`NotionDatabaseProperties`)
Retrieve properties of a Notion database.
- **Inputs**: `database_id` (str), `notion_secret` (str)
- **Outputs**: `api_run_model` (Data), `api_build_tool` (Tool)

### List Pages  (`NotionListPages`)
Query a Notion database with filtering and sorting. The input should be a JSON string containing the 'filter' and 'sorts' objects. Example input:
{"filter": {"property": "Status", "select": {"equals": "Done"}}, "sorts": [{"timestamp": "created_time", "direction": "descending"}]}
- **Inputs**: `query_json` (Message)
- **Outputs**: `api_run_model` (Data), `api_build_tool` (Tool)

### List Users  (`NotionUserList`)
Retrieve users from Notion.
- **Inputs**: `notion_secret` (str)
- **Outputs**: `api_run_model` (Data), `api_build_tool` (Tool)

### Page Content Viewer  (`NotionPageContent`)
Retrieve the content of a Notion page as plain text.
- **Inputs**: `notion_secret` (str), `page_id` (str)
- **Outputs**: `api_run_model` (Data), `api_build_tool` (Tool)

### Search  (`NotionSearch`)
Searches all pages and databases that have been shared with an integration.
- **Inputs**: `filter_value` (str), `notion_secret` (str), `query` (str)
- **Outputs**: `api_run_model` (Data), `api_build_tool` (Tool)

### Update Page Property  (`NotionPageUpdate`)
Update the properties of a Notion page.
- **Inputs**: `properties` (Message)
- **Outputs**: `api_run_model` (Data), `api_build_tool` (Tool)

## agentql

### Extract Web Data (`AgentQL`)
Extracts structured data from a web page using an AgentQL query or a Natural Language description.
- **Inputs**: `prompt` (Message), `query` (Message), `url` (Message)
- **Outputs**: `data` (Data)

## aiml

### AI/ML API (`AIMLModel`)
Generates text using AI/ML API LLMs.
- **Inputs**: `input_value` (Message), `system_message` (Message)
- **Outputs**: `text_output` (Message), `model_output` (LanguageModel)

### AI/ML API Embeddings (`AIMLEmbeddings`)
Generate embeddings using the AI/ML API.
- **Inputs**: `aiml_api_key` (str), `model_name` (str)
- **Outputs**: `embeddings` (Embeddings)

## altk

### ALTK Agent (`ALTK Agent`)
Advanced agent with both pre-tool validation and post-tool processing capabilities.
- **Inputs**: `agent_description` (Message), `context_id` (Message), `format_instructions` (Message), `input_value` (Message), `system_prompt` (Message), `tools` (Tool)
- **Outputs**: `response` (Message)

## amazon

### Amazon Bedrock (`AmazonBedrockModel`)
Generate text using Amazon Bedrock LLMs with the legacy ChatBedrock API. This component is deprecated. Please use Amazon Bedrock Converse instead for better compatibility, newer features, and improved conversation handling.
- **Inputs**: `endpoint_url` (Message), `input_value` (Message), `system_message` (Message)
- **Outputs**: `text_output` (Message), `model_output` (LanguageModel)

### Amazon Bedrock Converse (`AmazonBedrockConverseModel`)
Generate text using Amazon Bedrock LLMs with the modern Converse API for improved conversation handling.
- **Inputs**: `endpoint_url` (Message), `input_value` (Message), `system_message` (Message)
- **Outputs**: `text_output` (Message), `model_output` (LanguageModel)

### Amazon Bedrock Embeddings (`AmazonBedrockEmbeddings`)
Generate embeddings using Amazon Bedrock models.
- **Inputs**: `endpoint_url` (Message)
- **Outputs**: `embeddings` (Embeddings)

### S3 Bucket Uploader (`s3bucketuploader`)
Uploads files to S3 bucket.
- **Inputs**: `data_inputs` (Data)
- **Outputs**: `data` (NoneType)

## anthropic

### Anthropic (`AnthropicModel`)
Generate text using Anthropic's Messages API and models.
- **Inputs**: `base_url` (Message), `input_value` (Message), `system_message` (Message)
- **Outputs**: `text_output` (Message), `model_output` (LanguageModel)

## apify

### Apify Actors (`ApifyActors`)
Use Apify Actors to extract data from hundreds of places fast. This component can be used in a flow to retrieve data or as a tool with an agent.
- **Inputs**: `dataset_fields` (Message), `run_input` (Message)
- **Outputs**: `output` (Data), `tool` (Tool)

## arxiv

### arXiv (`ArXivComponent`)
Search and retrieve papers from arXiv.org
- **Inputs**: `search_query` (Message)
- **Outputs**: `dataframe` (DataFrame)

## assemblyai

### AssemblyAI Get Subtitles (`AssemblyAIGetSubtitles`)
Export your transcript in SRT or VTT format for subtitles and closed captions
- **Inputs**: `transcription_result` (Data)
- **Outputs**: `subtitles` (Data)

### AssemblyAI LeMUR (`AssemblyAILeMUR`)
Apply Large Language Models to spoken data using the AssemblyAI LeMUR framework
- **Inputs**: `prompt` (Message), `questions` (Message), `transcript_ids` (Message), `transcription_result` (Data)
- **Outputs**: `lemur_response` (Data)

### AssemblyAI List Transcripts (`AssemblyAIListTranscripts`)
Retrieve a list of transcripts from AssemblyAI with filtering options
- **Inputs**: `created_on` (Message)
- **Outputs**: `transcript_list` (Data)

### AssemblyAI Poll Transcript (`AssemblyAITranscriptionJobPoller`)
Poll for the status of a transcription job using AssemblyAI
- **Inputs**: `transcript_id` (Data)
- **Outputs**: `transcription_result` (Data)

### AssemblyAI Start Transcript (`AssemblyAITranscriptionJobCreator`)
Create a transcription job for an audio file using AssemblyAI with advanced options
- **Inputs**: `audio_file_url` (Message), `language_code` (Message), `speakers_expected` (Message)
- **Outputs**: `transcript_id` (Data)

## azure

### Azure OpenAI (`AzureOpenAIModel`)
Generate text using Azure OpenAI LLMs.
- **Inputs**: `azure_deployment` (Message), `azure_endpoint` (Message), `input_value` (Message), `system_message` (Message)
- **Outputs**: `text_output` (Message), `model_output` (LanguageModel)

### Azure OpenAI Embeddings (`AzureOpenAIEmbeddings`)
Generate embeddings using Azure OpenAI models.
- **Inputs**: `azure_deployment` (Message), `azure_endpoint` (Message)
- **Outputs**: `embeddings` (Embeddings)

## baidu

### Qianfan (`BaiduQianfanChatModel`)
Generate text using Baidu Qianfan LLMs.
- **Inputs**: `endpoint` (Message), `input_value` (Message), `system_message` (Message)
- **Outputs**: `text_output` (Message), `model_output` (LanguageModel)

## bing

### Bing Search API (`BingSearchAPI`)
Call the Bing Search API.
- **Inputs**: `bing_search_url` (Message), `input_value` (Message)
- **Outputs**: `dataframe` (DataFrame), `tool` (Tool)

## cassandra

### Cassandra (`Cassandra`)
Cassandra Vector Store with search capabilities
- **Inputs**: `body_search` (Message), `database_ref` (Message), `embedding` (Embeddings), `ingest_data` (Data/DataFrame), `keyspace` (Message), `search_query` (Message)
- **Outputs**: `search_results` (Data), `dataframe` (DataFrame)

### Cassandra Chat Memory (`CassandraChatMemory`)
Retrieves and store chat messages from Apache Cassandra.
- **Inputs**: `database_ref` (Message), `keyspace` (Message), `session_id` (Message), `table_name` (Message), `username` (Message)
- **Outputs**: `memory` (Memory)

### Cassandra Graph (`CassandraGraph`)
Cassandra Graph Vector Store
- **Inputs**: `database_ref` (Message), `embedding` (Embeddings), `ingest_data` (Data/DataFrame), `keyspace` (Message), `search_query` (Message), `table_name` (Message)
- **Outputs**: `search_results` (Data), `dataframe` (DataFrame)

## chroma

### Chroma DB (`Chroma`)
Chroma Vector Store with search capabilities
- **Inputs**: `embedding` (Embeddings), `ingest_data` (Data/DataFrame), `search_query` (Message)
- **Outputs**: `search_results` (Data), `dataframe` (DataFrame)

## cleanlab

### Cleanlab Evaluator (`CleanlabEvaluator`)
Evaluates any LLM response using Cleanlab and outputs trust score and explanation.
- **Inputs**: `prompt` (Message), `response` (Message), `system_prompt` (Message)
- **Outputs**: `response_passthrough` (Message), `score` (number/float), `explanation` (Message)

### Cleanlab RAG Evaluator (`CleanlabRAGEvaluator`)
Evaluates context, query, and response from a RAG pipeline using Cleanlab and outputs trust metrics.
- **Inputs**: `context` (Message), `query` (Message), `response` (Message)
- **Outputs**: `response_passthrough` (Message), `trust_score` (number/float), `trust_explanation` (Message), `other_scores` (Data/dict), `evaluation_summary` (Message)

### Cleanlab Remediator (`CleanlabRemediator`)
Remediates an untrustworthy response based on trust score from the Cleanlab Evaluator, score threshold, and message handling settings.
- **Inputs**: `explanation` (Message), `response` (Message), `score` (number)
- **Outputs**: `remediated_response` (Message)

## clickhouse

### ClickHouse (`Clickhouse`)
ClickHouse Vector Store with search capabilities
- **Inputs**: `embedding` (Embeddings), `ingest_data` (Data/DataFrame), `search_query` (Message)
- **Outputs**: `search_results` (Data), `dataframe` (DataFrame)

## cloudflare

### Cloudflare Workers AI Embeddings (`CloudflareWorkersAIEmbeddings`)
Generate embeddings using Cloudflare Workers AI models.
- **Inputs**: `account_id` (Message), `api_base_url` (Message), `model_name` (Message)
- **Outputs**: `embeddings` (Embeddings)

## cohere

### Cohere Embeddings (`CohereEmbeddings`)
Generate embeddings using Cohere models.
- **Inputs**: `truncate` (Message), `user_agent` (Message)
- **Outputs**: `embeddings` (Embeddings)

### Cohere Language Models (`CohereModel`)
Generate text using Cohere LLMs.
- **Inputs**: `input_value` (Message), `system_message` (Message)
- **Outputs**: `text_output` (Message), `model_output` (LanguageModel)

### Cohere Rerank (`CohereRerank`)
Rerank documents using the Cohere API.
- **Inputs**: `search_query` (Message), `search_results` (Data)
- **Outputs**: `reranked_documents` (Data)

## cometapi

### CometAPI (`CometAPIModel`)
All AI Models in One API 500+ AI Models
- **Inputs**: `input_value` (Message), `system_message` (Message)
- **Outputs**: `text_output` (Message), `model_output` (LanguageModel)

## composio

### AgentQL (`ComposioAgentQLAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Agiled (`ComposioAgiledAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Airtable (`ComposioAirtableAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Apollo (`ComposioApolloAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Asana (`ComposioAsanaAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Attio (`ComposioAttioAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Bitbucket (`ComposioBitbucketAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Bolna (`ComposioBolnaAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Brightdata (`ComposioBrightdataAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Calendly (`ComposioCalendlyAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Canva (`ComposioCanvaAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Canvas (`ComposioCanvasAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Coda (`ComposioCodaAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Composio Tools (`ComposioAPI`)
Use Composio toolset to run actions with your agent
- **Inputs**: `entity_id` (Message)
- **Outputs**: `tools` (Tool)

### Contentful (`ComposioContentfulAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Digicert (`ComposioDigicertAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Discord (`ComposioDiscordAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Dropbox (`ComposioDropboxAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### ElevenLabs (`ComposioElevenLabsAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Exa (`ComposioExaAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Figma (`ComposioFigmaAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Finage (`ComposioFinageAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Firecrawl (`ComposioFirecrawlAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Fireflies (`ComposioFirefliesAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Fixer (`ComposioFixerAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Flexisign (`ComposioFlexisignAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Freshdesk (`ComposioFreshdeskAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### GitHub (`ComposioGitHubAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Gmail (`ComposioGmailAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Google Classroom (`ComposioGoogleclassroomAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### GoogleBigQuery (`ComposioGoogleBigQueryAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### GoogleCalendar (`ComposioGoogleCalendarAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### GoogleDocs (`ComposioGoogleDocsAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### GoogleMeet (`ComposioGooglemeetAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### GoogleSheets (`ComposioGoogleSheetsAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### GoogleTasks (`ComposioGoogleTasksAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Heygen (`ComposioHeygenAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Instagram (`ComposioInstagramAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Jira (`ComposioJiraAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Jotform (`ComposioJotformAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Klaviyo (`ComposioKlaviyoAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Linear (`ComposioLinearAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Listennotes (`ComposioListennotesAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Mem0 (`ComposioMem0APIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Miro (`ComposioMiroAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Missive (`ComposioMissiveAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Notion (`ComposioNotionAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### OneDrive (`ComposioOneDriveAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Outlook (`ComposioOutlookAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Pandadoc (`ComposioPandadocAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### PeopleDataLabs (`ComposioPeopleDataLabsAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### PerplexityAI (`ComposioPerplexityAIAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Reddit (`ComposioRedditAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### SerpAPI (`ComposioSerpAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Slack (`ComposioSlackAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Slackbot (`ComposioSlackbotAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Snowflake (`ComposioSnowflakeAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Supabase (`ComposioSupabaseAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Tavily (`ComposioTavilyAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### TimelinesAI (`ComposioTimelinesAIAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Todoist (`ComposioTodoistAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### Wrike (`ComposioWrikeAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

### YouTube (`ComposioYoutubeAPIComponent`)
- **Inputs**: `entity_id` (Message)
- **Outputs**: `dataFrame` (DataFrame)

## confluence

### Confluence (`Confluence`)
Confluence wiki collaboration platform
- **Inputs**: `api_key` (str), `cloud` (bool), `content_format` (str)
- **Outputs**: `data` (Data)

## couchbase

### Couchbase (`Couchbase`)
Couchbase Vector Store with search capabilities
- **Inputs**: `embedding` (Embeddings), `ingest_data` (Data/DataFrame), `search_query` (Message)
- **Outputs**: `search_results` (Data), `dataframe` (DataFrame)

## crewai

### CrewAI Agent (`CrewAIAgentComponent`)
Represents an agent of CrewAI.
- **Inputs**: `backstory` (Message), `goal` (Message), `llm` (LanguageModel), `role` (Message), `tools` (Tool)
- **Outputs**: `output` (NoneType)

### Hierarchical Crew (`HierarchicalCrewComponent`)
Represents a group of agents, defining how they should collaborate and the tasks they should perform.
- **Inputs**: `agents` (Agent), `function_calling_llm` (LanguageModel), `manager_agent` (Agent), `manager_llm` (LanguageModel), `tasks` (HierarchicalTask)
- **Outputs**: `output` (Message)

### Hierarchical Task (`HierarchicalTaskComponent`)
Each task must have a description, an expected output and an agent responsible for execution.
- **Inputs**: `expected_output` (Message), `task_description` (Message), `tools` (Tool)
- **Outputs**: `task_output` (HierarchicalTask)

### Sequential Crew (`SequentialCrewComponent`)
Represents a group of agents with tasks that are executed sequentially.
- **Inputs**: `function_calling_llm` (LanguageModel), `tasks` (SequentialTask)
- **Outputs**: `output` (Message)

### Sequential Task (`SequentialTaskComponent`)
Each task must have a description, an expected output and an agent responsible for execution.
- **Inputs**: `agent` (Agent), `expected_output` (Message), `task` (SequentialTask), `task_description` (Message), `tools` (Tool)
- **Outputs**: `task_output` (SequentialTask)

### Sequential Task Agent (`SequentialTaskAgentComponent`)
Creates a CrewAI Task and its associated Agent.
- **Inputs**: `backstory` (Message), `expected_output` (Message), `goal` (Message), `llm` (LanguageModel), `previous_task` (SequentialTask), `role` (Message)
- **Outputs**: `task_output` (SequentialTask)

## cuga

### Cuga (`Cuga`)
Define the Cuga agent's instructions, then assign it a task.
- **Inputs**: `agent_description` (Message), `input_value` (Message), `instructions` (Message), `tools` (Tool), `web_apps` (Message)
- **Outputs**: `response` (Message)

## custom_component

### Custom Component (`CustomComponent`)
Use as a template to create your own component.
- **Inputs**: `input_value` (Message)
- **Outputs**: `output` (Data)

## data_source

### API Request (`APIRequest`)
Make HTTP requests using URL or cURL commands.
- **Inputs**: `body` (Data), `headers` (Data), `query_params` (Data), `url_input` (Message)
- **Outputs**: `data` (Data)

### Load CSV (`CSVtoData`)
Load a CSV file, CSV from a file path, or a valid CSV string and convert it to a list of Data
- **Inputs**: `csv_path` (Message), `csv_string` (Message), `text_key` (Message)
- **Outputs**: `data_list` (Data)

### Load JSON (`JSONtoData`)
Convert a JSON file, JSON from a file path, or a JSON string to a Data object or a list of Data objects
- **Inputs**: `json_path` (Message), `json_string` (Message)
- **Outputs**: `data` (Data)

### Mock Data (`MockDataGenerator`)
Generate mock data for testing and development.
- **Outputs**: `dataframe_output` (DataFrame), `message_output` (Message), `data_output` (Data)

### News Search (`NewsSearch`)
Searches Google News via RSS. Returns clean article data.
- **Inputs**: `query` (Message)
- **Outputs**: `articles` (DataFrame)

### RSS Reader (`RSSReaderSimple`)
Fetches and parses an RSS feed.
- **Inputs**: `rss_url` (Message)
- **Outputs**: `articles` (DataFrame)

### SQL Database (`SQLComponent`)
Executes SQL queries on SQLAlchemy-compatible databases.
- **Inputs**: `database_url` (Message), `query` (Message)
- **Outputs**: `run_sql_query` (DataFrame)

### URL (`URLComponent`)
Fetch content from one or more web pages, following links recursively.
- **Inputs**: `headers` (DataFrame)
- **Outputs**: `page_results` (DataFrame), `raw_results` (Message)

### Web Search (`UnifiedWebSearch`)
Search the web, news, or RSS feeds.
- **Inputs**: `query` (Message)
- **Outputs**: `results` (DataFrame)

## datastax

### Astra Assistant Agent (`Astra Assistant Agent`)
Manages Assistant Interactions
- **Inputs**: `env_set` (Message), `input_assistant_id` (Message), `input_thread_id` (Message), `input_tools` (Tool), `instructions` (Message), `user_message` (Message)
- **Outputs**: `assistant_response` (Message), `tool_output` (Message), `output_thread_id` (Message), `output_assistant_id` (Message), `output_vs_id` (Message)

### Astra DB (`AstraDB`)
Ingest and search documents in Astra DB
- **Inputs**: `embedding_model` (Embeddings), `ingest_data` (Data/DataFrame), `lexical_terms` (Message), `search_query` (Message)
- **Outputs**: `search_results` (Data), `dataframe` (DataFrame), `vectorstoreconnection` (VectorStore)

### Astra DB CQL (`AstraDBCQLToolComponent`)
Create a tool to get transactional data from DataStax Astra DB CQL Table
- **Inputs**: `api_endpoint` (str), `autodetect_collection` (bool), `collection_name` (str)
- **Outputs**: `api_run_model` (Data), `api_build_tool` (Tool)

### Astra DB Chat Memory (`AstraDBChatMemory`)
Retrieves and stores chat messages from Astra DB.
- **Inputs**: `session_id` (Message)
- **Outputs**: `memory` (Memory)

### Astra DB Graph (`AstraDBGraph`)
Implementation of Graph Vector Store using Astra DB
- **Inputs**: `ingest_data` (Data/DataFrame), `search_query` (Message)
- **Outputs**: `search_results` (Data), `dataframe` (DataFrame)

### Astra DB Tool (`AstraDBTool`)
Tool to run hybrid vector and metadata search on DataStax Astra DB Collection
- **Inputs**: `api_endpoint` (str), `autodetect_collection` (bool), `collection_name` (str)
- **Outputs**: `api_run_model` (Data), `api_build_tool` (Tool)

### Astra Vectorize (`AstraVectorize`)
Configuration options for Astra Vectorize server-side embeddings. 
- **Inputs**: `api_key_name` (Message), `model_name` (Message)
- **Outputs**: `config` (dict)

### Create Assistant (`AssistantsCreateAssistant`)
Creates an Assistant and returns it's id
- **Inputs**: `env_set` (Message)
- **Outputs**: `assistant_id` (Message)

### Create Assistant Thread (`AssistantsCreateThread`)
Creates a thread and returns the thread id
- **Inputs**: `env_set` (Message)
- **Outputs**: `thread_id` (Message)

### Dotenv (`Dotenv`)
Load .env file into env vars
- **Inputs**: `dotenv_file_content` (Message)
- **Outputs**: `env_set` (Message)

### Get Assistant name (`AssistantsGetAssistantName`)
Assistant by id
- **Inputs**: `env_set` (Message)
- **Outputs**: `assistant_name` (Message)

### Get Environment Variable (`GetEnvVar`)
Gets the value of an environment variable from the system.
- **Inputs**: `env_var_name` (str)
- **Outputs**: `env_var_value` (Message)

### Graph RAG (`GraphRAG`)
Graph RAG traversal for vector store.
- **Inputs**: `embedding_model` (Embeddings), `search_query` (Message), `vector_store` (VectorStore)
- **Outputs**: `search_results` (Data), `dataframe` (DataFrame)

### Hyper-Converged Database (`HCD`)
Implementation of Vector Store using Hyper-Converged Database (HCD) with search capabilities
- **Inputs**: `ca_certificate` (Message), `embedding` (Embeddings/dict), `ingest_data` (Data/DataFrame), `search_query` (Message)
- **Outputs**: `search_results` (Data), `dataframe` (DataFrame)

### List Assistants (`AssistantsListAssistants`)
Returns a list of assistant id's
- **Outputs**: `assistants` (Message)

### Run Assistant (`AssistantsRun`)
Executes an Assistant Run against a thread
- **Inputs**: `assistant_id` (Message), `env_set` (Message), `thread_id` (Message), `user_message` (Message)
- **Outputs**: `assistant_response` (Message)

## deepseek

### DeepSeek (`DeepSeekModelComponent`)
Generate text using DeepSeek LLMs.
- **Inputs**: `input_value` (Message), `system_message` (Message)
- **Outputs**: `text_output` (Message), `model_output` (LanguageModel)

## docling

### Chunk DoclingDocument (`ChunkDoclingDocument`)
Use the DocumentDocument chunkers to split the document into chunks.
- **Inputs**: `data_inputs` (Data/DataFrame), `doc_key` (Message)
- **Outputs**: `dataframe` (DataFrame)

### Docling (`DoclingInline`)
Uses Docling to process input documents running the Docling models locally.
- **Inputs**: `file_path` (Data/Message), `pic_desc_llm` (LanguageModel)
- **Outputs**: `dataframe` (DataFrame)

### Docling Serve (`DoclingRemote`)
Uses Docling to process input documents connecting to your instance of Docling Serve.
- **Inputs**: `file_path` (Data/Message)
- **Outputs**: `dataframe` (DataFrame)

### Export DoclingDocument (`ExportDoclingDocument`)
Export DoclingDocument to markdown, html or other formats.
- **Inputs**: `data_inputs` (Data/DataFrame), `doc_key` (Message)
- **Outputs**: `data` (Data), `dataframe` (DataFrame)

## duckduckgo

### DuckDuckGo Search (`DuckDuckGoSearchComponent`)
Search the web using DuckDuckGo with customizable result limits
- **Inputs**: `input_value` (Message)
- **Outputs**: `dataframe` (DataFrame)

## elastic

### Elasticsearch (`Elasticsearch`)
Elasticsearch Vector Store with with advanced, customizable search capabilities.
- **Inputs**: `embedding` (Embeddings), `ingest_data` (Data/DataFrame), `search_query` (Message)
- **Outputs**: `search_results` (Data), `dataframe` (DataFrame)

### OpenSearch (`OpenSearchVectorStoreComponent`)
Store and search documents using OpenSearch with hybrid semantic and keyword search capabilities.
- **Inputs**: `docs_metadata` (Data), `embedding` (Embeddings), `filter_expression` (Message), `ingest_data` (Data/DataFrame), `search_query` (Message)
- **Outputs**: `search_results` (Data), `dataframe` (DataFrame), `vectorstoreconnection` (VectorStore)

### OpenSearch (Multi-Model Multi-Embedding) (`OpenSearchVectorStoreComponentMultimodalMultiEmbedding`)
Store and search documents using OpenSearch with multi-model hybrid semantic and keyword search.
- **Inputs**: `docs_metadata` (Data), `embedding` (Embeddings), `filter_expression` (Message), `ingest_data` (Data/DataFrame), `search_query` (Message)
- **Outputs**: `search_results` (Data), `dataframe` (DataFrame), `vectorstoreconnection` (VectorStore)

## embeddings

### Embedding Similarity (`EmbeddingSimilarityComponent`)
Compute selected form of similarity between two embedding vectors.
- **Inputs**: `embedding_vectors` (Data)
- **Outputs**: `similarity_data` (Data)

### Text Embedder (`TextEmbedderComponent`)
Generate embeddings for a given message using the specified embedding model.
- **Inputs**: `embedding_model` (Embeddings), `message` (Message)
- **Outputs**: `embeddings` (Data)

## exa

### Exa Search (`ExaSearch`)
Exa Search toolkit for search and content retrieval
- **Inputs**: `metaphor_api_key` (str), `search_num_results` (int), `similar_num_results` (int)
- **Outputs**: `tools` (Tool)

## files_and_knowledge

### Directory (`Directory`)
Recursively load files from a directory.
- **Inputs**: `path` (Message)
- **Outputs**: `dataframe` (DataFrame)

### Knowledge Ingestion (`KnowledgeIngestion`)
Create or update knowledge in Langflow.
- **Inputs**: `input_df` (Data/DataFrame)
- **Outputs**: `dataframe_output` (Data)

### Knowledge Retrieval (`KnowledgeRetrieval`)
Search and retrieve data from knowledge.
- **Inputs**: `search_query` (Message)
- **Outputs**: `retrieve_data` (DataFrame)

### Read File (`File`)
Loads and returns the content from uploaded files.
- **Inputs**: `file_path` (Data/Message)
- **Outputs**: `message` (Message)

### Write File (`SaveToFile`)
Save data to local file, AWS S3, or Google Drive in the selected format.
- **Inputs**: `input` (Data/DataFrame/Message)
- **Outputs**: `message` (Message)

## firecrawl

### Firecrawl Crawl API (`FirecrawlCrawlApi`)
Crawls a URL and returns the results.
- **Inputs**: `crawlerOptions` (Data), `scrapeOptions` (Data), `url` (Message)
- **Outputs**: `data` (Data)

### Firecrawl Extract API (`FirecrawlExtractApi`)
Extracts data from a URL.
- **Inputs**: `prompt` (Message), `schema` (Data), `urls` (Message)
- **Outputs**: `data` (Data)

### Firecrawl Map API (`FirecrawlMapApi`)
Maps a URL and returns the results.
- **Inputs**: `urls` (Message)
- **Outputs**: `data` (Data)

### Firecrawl Scrape API (`FirecrawlScrapeApi`)
Scrapes a URL and returns the results.
- **Inputs**: `extractorOptions` (Data), `scrapeOptions` (Data), `url` (Message)
- **Outputs**: `data` (Data)

## flow_controls

### Condition (`DataConditionalRouter`)
Route Data object(s) based on a condition applied to a specified key, including boolean validation.
- **Inputs**: `compare_value` (Message), `data_input` (Data), `key_name` (Message)
- **Outputs**: `true_output` (Data), `false_output` (Data)

### Flow as Tool (`FlowTool`)
Construct a Tool from a function that runs the loaded Flow.
- **Inputs**: `flow_name` (str), `return_direct` (bool), `tool_description` (str)
- **Outputs**: `api_build_tool` (Tool)

### If-Else (`ConditionalRouter`)
Routes an input message to a corresponding output based on text comparison.
- **Inputs**: `false_case_message` (Message), `input_text` (Message), `match_text` (Message), `true_case_message` (Message)
- **Outputs**: `true_result` (Message), `false_result` (Message)

### Listen (`Listen`)
A component to listen for a notification.
- **Inputs**: `context_key` (Message)
- **Outputs**: `data` (Data)

### Loop (`LoopComponent`)
Iterates over a list of Data or Message objects, processing one item at a time and aggregating results from loop inputs. Message objects are automatically converted to Data objects for consistent processing.
- **Inputs**: `data` (DataFrame)
- **Outputs**: `item` (Data), `done` (DataFrame)

### Notify (`Notify`)
A component to generate a notification to Get Notified component.
- **Inputs**: `input_value` (Data/Message/DataFrame)
- **Outputs**: `result` (Data)

### Pass (`Pass`)
Forwards the input message, unchanged.
- **Inputs**: `ignored_message` (Message), `input_message` (Message)
- **Outputs**: `output_message` (Message)

### Run Flow (`RunFlow`)
Executes another flow from within the same project. Can also be used as a tool for agents. 
 **Select a Flow to use the tool mode**
- **Inputs**: `session_id` (Message)

### Sub Flow (`SubFlow`)
Generates a Component from a Flow, with all of its inputs, and 
- **Inputs**: `flow_name` (str)
- **Outputs**: `flow_outputs` (Data)

## git

### Git (`GitLoaderComponent`)
Load and filter documents from a local or remote Git repository. Use a local repo path or clone from a remote URL.
- **Inputs**: `branch` (Message), `clone_url` (Message), `content_filter` (Message), `file_filter` (Message), `repo_path` (Message)
- **Outputs**: `data` (Data)

### GitExtractor (`GitExtractorComponent`)
Analyzes a Git repository and returns file contents and complete repository information
- **Inputs**: `repository_url` (Message)
- **Outputs**: `text_based_file_contents` (Message), `directory_structure` (Message), `repository_info` (Data), `statistics` (Data), `files_content` (Data)

## glean

### Glean Search API (`GleanSearchAPIComponent`)
Search using Glean's API.
- **Inputs**: `query` (Message)
- **Outputs**: `dataframe` (DataFrame)

## google

### BigQuery (`BigQueryExecutor`)
Execute SQL queries on Google BigQuery.
- **Inputs**: `query` (Message)
- **Outputs**: `query_results` (DataFrame)

### Gmail Loader (`GmailLoaderComponent`)
Loads emails from Gmail using provided credentials.
- **Inputs**: `label_ids` (Message), `max_results` (Message)
- **Outputs**: `data` (Data)

### Google Drive Loader (`GoogleDriveComponent`)
Loads documents from Google Drive using provided credentials.
- **Inputs**: `document_id` (Message)
- **Outputs**: `docs` (Data)

### Google Drive Search (`GoogleDriveSearchComponent`)
Searches Google Drive files using provided credentials and query parameters.
- **Inputs**: `query_string` (Message), `search_term` (Message)
- **Outputs**: `doc_urls` (Text), `doc_ids` (Text), `doc_titles` (Text), `Data` (Data)

### Google Generative AI (`GoogleGenerativeAIModel`)
Generate text using Google Generative AI.
- **Inputs**: `input_value` (Message), `system_message` (Message)
- **Outputs**: `text_output` (Message), `model_output` (LanguageModel)

### Google Generative AI Embeddings (`Google Generative AI Embeddings`)
Connect to Google's generative AI embeddings service using the GoogleGenerativeAIEmbeddings class, found in the langchain-google-genai package.
- **Inputs**: `model_name` (Message)
- **Outputs**: `embeddings` (Embeddings)

### Google OAuth Token (`GoogleOAuthToken`)
Generates a JSON string with your Google OAuth token.
- **Inputs**: `scopes` (Message)
- **Outputs**: `output` (Data)

### Google Search API (`GoogleSearchAPICore`)
Call Google Search API and return results as a DataFrame.
- **Inputs**: `input_value` (Message)
- **Outputs**: `results` (DataFrame)

### Google Serper API (`GoogleSerperAPICore`)
Call the Serper.dev Google Search API.
- **Inputs**: `input_value` (Message)
- **Outputs**: `results` (DataFrame)

## groq

### Groq (`GroqModel`)
Generate text using Groq.
- **Inputs**: `base_url` (Message), `input_value` (Message), `system_message` (Message)
- **Outputs**: `text_output` (Message), `model_output` (LanguageModel)

## homeassistant

### Home Assistant Control (`HomeAssistantControl`)
A very simple tool to control Home Assistant devices. Only action (turn_on, turn_off, toggle) and entity_id need to be provided.
- **Inputs**: `base_url` (str), `default_action` (str), `default_entity_id` (str)
- **Outputs**: `api_run_model` (Data), `api_build_tool` (Tool)

### List Home Assistant States (`ListHomeAssistantStates`)
Retrieve states from Home Assistant. The agent only needs to specify 'filter_domain' (optional). Token and base_url are not exposed to the agent.
- **Inputs**: `base_url` (str), `filter_domain` (str), `ha_token` (str)
- **Outputs**: `api_run_model` (Data), `api_build_tool` (Tool)

## huggingface

### Hugging Face (`HuggingFaceModel`)
Generate text using Hugging Face Inference APIs.
- **Inputs**: `input_value` (Message), `system_message` (Message)
- **Outputs**: `text_output` (Message), `model_output` (LanguageModel)

### Hugging Face Embeddings Inference (`HuggingFaceInferenceAPIEmbeddings`)
Generate embeddings using Hugging Face Text Embeddings Inference (TEI)
- **Inputs**: `inference_endpoint` (Message), `model_name` (Message)
- **Outputs**: `embeddings` (Embeddings)

## ibm

### IBM watsonx.ai (`IBMwatsonxModel`)
Generate text using IBM watsonx.ai foundation models.
- **Inputs**: `input_value` (Message), `system_message` (Message)
- **Outputs**: `text_output` (Message), `model_output` (LanguageModel)

### IBM watsonx.ai Embeddings (`WatsonxEmbeddingsComponent`)
Generate embeddings using IBM watsonx.ai models.
- **Inputs**: `api_key` (str), `input_text` (bool), `model_name` (str)
- **Outputs**: `embeddings` (Embeddings)

## icosacomputing

### Combinatorial Reasoner (`Combinatorial Reasoner`)
Uses Combinatorial Optimization to construct an optimal prompt with embedded reasons. Sign up here:
https://forms.gle/oWNv2NKjBNaqqvCx6
- **Inputs**: `prompt` (Message)
- **Outputs**: `optimized_prompt` (Message), `reasons` (Data)

## input_output

### Chat Input (`ChatInput`)
Get chat inputs from the Playground.
- **Inputs**: `context_id` (Message), `sender_name` (Message), `session_id` (Message)
- **Outputs**: `message` (Message)

### Chat Output (`ChatOutput`)
Display a chat message in the Playground.
- **Inputs**: `context_id` (Message), `data_template` (Message), `input_value` (Data/DataFrame/Message), `sender_name` (Message), `session_id` (Message)
- **Outputs**: `message` (Message)

### Text Input (`TextInput`)
Get user text inputs.
- **Inputs**: `input_value` (Message)
- **Outputs**: `text` (Message)

### Text Output (`TextOutput`)
Sends text output via API.
- **Inputs**: `input_value` (Message)
- **Outputs**: `text` (Message)

### Webhook (`Webhook`)
- **Inputs**: `data` (Message)
- **Outputs**: `output_data` (Data)

## jigsawstack

### AI Scraper (`JigsawStackAIScraper`)
Scrape any website instantly and get consistent structured data         in seconds without writing any css selector code
- **Inputs**: `element_prompts` (Message), `html` (Message), `root_element_selector` (Message), `url` (Message)
- **Outputs**: `scrape_results` (Data)

### AI Web Search (`JigsawStackAISearch`)
Effortlessly search the Web and get access to high-quality results powered with AI.
- **Inputs**: `query` (Message)
- **Outputs**: `search_results` (Data), `content_text` (Message)

### File Read (`JigsawStackFileRead`)
Read any previously uploaded file seamlessly from         JigsawStack File Storage and use it in your AI applications.
- **Inputs**: `api_key` (str), `key` (str)
- **Outputs**: `file_path` (Data)

### File Upload (`JigsawStackFileUpload`)
Store any file seamlessly on JigsawStack File Storage and use it in your AI applications.         Supports various file types including images, documents, and more.
- **Inputs**: `api_key` (str), `key` (str), `overwrite` (bool)
- **Outputs**: `file_upload_result` (Data)

### Image Generation (`JigsawStackImageGeneration`)
Generate an image based on the given text by employing AI models like Flux,         Stable Diffusion, and other top models.
- **Inputs**: `aspect_ratio` (Message), `file_store_key` (Message), `negative_prompt` (Message), `prompt` (Message), `url` (Message)
- **Outputs**: `image_generation_results` (Data)

### NSFW Detection (`JigsawStackNSFW`)
Detect if image/video contains NSFW content
- **Inputs**: `api_key` (str), `url` (str)
- **Outputs**: `nsfw_result` (Data)

### Object Detection (`JigsawStackObjectDetection`)
Perform object detection on images using JigsawStack's Object Detection Model,         capable of image grounding, segmentation and computer use.
- **Inputs**: `file_store_key` (Message), `prompts` (Message), `url` (Message)
- **Outputs**: `object_detection_results` (Data)

### Sentiment Analysis (`JigsawStackSentiment`)
Analyze sentiment of text using JigsawStack AI
- **Inputs**: `text` (Message)
- **Outputs**: `sentiment_data` (Data), `sentiment_text` (Message)

### Text Translate (`JigsawStackTextTranslate`)
Translate text from one language to another with support for multiple text formats.
- **Inputs**: `text` (Message)
- **Outputs**: `translation_results` (Data)

### Text to SQL (`JigsawStackTextToSQL`)
Convert natural language to SQL queries using JigsawStack AI
- **Inputs**: `prompt` (Message), `sql_schema` (Message)
- **Outputs**: `sql_query` (Data)

### VOCR (`JigsawStackVOCR`)
Extract data from any document type in a consistent structure with fine-tuned         vLLMs for the highest accuracy
- **Inputs**: `prompts` (Message)
- **Outputs**: `vocr_results` (Data)

## langchain_utilities

### CSV Agent (`CSVAgent`)
Construct a CSV agent from a CSV and tools.
- **Inputs**: `agent_description` (Message), `input_value` (Message), `llm` (LanguageModel), `path` (str/Message)
- **Outputs**: `response` (Message), `agent` (AgentExecutor)

### Character Text Splitter (`CharacterTextSplitter`)
Split text by number of characters.
- **Inputs**: `data_input` (Document/Data), `separator` (Message)
- **Outputs**: `data` (Data)

### ConversationChain (`ConversationChain`)
Chain to have a conversation and load context from memory.
- **Inputs**: `input_value` (Message), `llm` (LanguageModel), `memory` (BaseChatMemory)
- **Outputs**: `text` (Message)

### Fake Embeddings (`LangChainFakeEmbeddings`)
Generate fake embeddings, useful for initial testing and connecting components.
- **Inputs**: `dimensions` (int)
- **Outputs**: `embeddings` (Embeddings)

### HTML Link Extractor (`HtmlLinkExtractor`)
Extract hyperlinks from HTML content.
- **Inputs**: `data_input` (Document/Data)
- **Outputs**: `data` (Data)

### JsonAgent (`JsonAgent`)
Construct a json agent from an LLM and tools.
- **Inputs**: `agent_description` (Message), `input_value` (Message), `llm` (LanguageModel)
- **Outputs**: `response` (Message), `agent` (AgentExecutor)

### LLMCheckerChain (`LLMCheckerChain`)
Chain for question-answering with self-verification.
- **Inputs**: `input_value` (Message), `llm` (LanguageModel)
- **Outputs**: `text` (Message)

### LLMMathChain (`LLMMathChain`)
Chain that interprets a prompt and executes python code to do math.
- **Inputs**: `input_value` (Message), `llm` (LanguageModel)
- **Outputs**: `text` (Message)

### Language Recursive Text Splitter (`LanguageRecursiveTextSplitter`)
Split text into chunks of a specified length based on language.
- **Inputs**: `data_input` (Document/Data)
- **Outputs**: `data` (Data)

### Natural Language Text Splitter (`NaturalLanguageTextSplitter`)
Split text based on natural language boundaries, optimized for a specified language.
- **Inputs**: `data_input` (Document/Data), `language` (Message), `separator` (Message)
- **Outputs**: `data` (Data)

### Natural Language to SQL (`SQLGenerator`)
Generate SQL from natural language.
- **Inputs**: `db` (SQLDatabase), `input_value` (Message), `llm` (LanguageModel), `prompt` (Message)
- **Outputs**: `text` (Message)

### OpenAI Tools Agent (`OpenAIToolsAgent`)
Agent that uses tools via openai-tools.
- **Inputs**: `agent_description` (Message), `chat_history` (Data), `input_value` (Message), `llm` (LanguageModel/ToolEnabledLanguageModel), `system_prompt` (Message), `tools` (Tool)
- **Outputs**: `response` (Message), `agent` (AgentExecutor)

### OpenAPI Agent (`OpenAPIAgent`)
Agent to interact with OpenAPI API.
- **Inputs**: `agent_description` (Message), `input_value` (Message), `llm` (LanguageModel)
- **Outputs**: `response` (Message), `agent` (AgentExecutor)

### Prompt Hub (`LangChain Hub Prompt`)
Prompt Component that uses LangChain Hub prompts
- **Inputs**: `langchain_api_key` (str), `langchain_hub_prompt` (str)
- **Outputs**: `prompt` (Message)

### Recursive Character Text Splitter (`RecursiveCharacterTextSplitter`)
Split text trying to keep all related text together.
- **Inputs**: `data_input` (Document/Data), `separators` (Message)
- **Outputs**: `data` (Data)

### Retrieval QA (`RetrievalQA`)
Chain for question-answering querying sources from a retriever.
- **Inputs**: `input_value` (Message), `llm` (LanguageModel), `memory` (BaseChatMemory), `retriever` (Retriever)
- **Outputs**: `text` (Message)

### Runnable Executor (`RunnableExecutor`)
Execute a runnable. It will try to guess the input and output keys.
- **Inputs**: `input_key` (Message), `input_value` (Message), `output_key` (Message), `runnable` (Chain/AgentExecutor/Agent/Runnable)
- **Outputs**: `text` (Message)

### SQLAgent (`SQLAgent`)
Construct an SQL agent from an LLM and tools.
- **Inputs**: `agent_description` (Message), `database_uri` (Message), `extra_tools` (Tool), `input_value` (Message), `llm` (LanguageModel)
- **Outputs**: `response` (Message), `agent` (AgentExecutor)

### SQLDatabase (`SQLDatabase`)
SQL Database
- **Inputs**: `uri` (str)
- **Outputs**: `SQLDatabase` (SQLDatabase)

### Self Query Retriever (`SelfQueryRetriever`)
Retriever that uses a vector store and an LLM to generate the vector store queries.
- **Inputs**: `attribute_infos` (Data), `document_content_description` (Message), `llm` (LanguageModel), `query` (Message), `vectorstore` (VectorStore)
- **Outputs**: `documents` (Data)

### Semantic Text Splitter (`SemanticTextSplitter`)
Split text into semantically meaningful chunks using semantic similarity.
- **Inputs**: `data_inputs` (Data), `embeddings` (Embeddings), `sentence_split_regex` (Message)
- **Outputs**: `chunks` (Data)

### Spider Web Crawler & Scraper (`SpiderTool`)
Spider API for web crawling and scraping.
- **Inputs**: `blacklist` (str), `depth` (int), `limit` (int)
- **Outputs**: `content` (Data)

### Tool Calling Agent (`ToolCallingAgent`)
An agent designed to utilize various tools seamlessly within workflows.
- **Inputs**: `agent_description` (Message), `chat_history` (Data), `input_value` (Message), `llm` (LanguageModel), `system_prompt` (Message), `tools` (Tool)
- **Outputs**: `response` (Message), `agent` (AgentExecutor)

### VectorStoreInfo (`VectorStoreInfo`)
Information about a VectorStore
- **Inputs**: `input_vectorstore` (VectorStore), `vectorstore_description` (Message), `vectorstore_name` (Message)
- **Outputs**: `info` (VectorStoreInfo)

### VectorStoreRouterAgent (`VectorStoreRouterAgent`)
Construct an agent from a Vector Store Router.
- **Inputs**: `agent_description` (Message), `input_value` (Message), `llm` (LanguageModel), `vectorstores` (VectorStoreInfo)
- **Outputs**: `response` (Message), `agent` (AgentExecutor)

### XML Agent (`XMLAgent`)
Agent that uses tools formatting instructions as xml to the Language Model.
- **Inputs**: `agent_description` (Message), `chat_history` (Data), `input_value` (Message), `llm` (LanguageModel), `system_prompt` (Message), `tools` (Tool)
- **Outputs**: `response` (Message), `agent` (AgentExecutor)

## langwatch

### LangWatch Evaluator (`LangWatchEvaluator`)
Evaluates various aspects of language models using LangWatch's evaluation endpoints.
- **Inputs**: `contexts` (Message), `expected_output` (Message), `input` (Message), `output` (Message)
- **Outputs**: `evaluation_result` (Data)

## llm_operations

### Batch Run (`BatchRunComponent`)
Runs an LLM on each row of a DataFrame column. If no column is specified, all columns are used.
- **Inputs**: `column_name` (Message), `df` (DataFrame), `output_column_name` (Message), `system_message` (Message)
- **Outputs**: `batch_results` (DataFrame)

### LLM Selector (`LLMSelectorComponent`)
Routes the input to the most appropriate LLM based on OpenRouter model specifications
- **Inputs**: `input_value` (Message), `judge_llm` (LanguageModel), `models` (LanguageModel)
- **Outputs**: `output` (Message), `selected_model_info` (Data), `routing_decision` (Message)

### Smart Router (`SmartRouter`)
Routes an input message using LLM-based categorization.
- **Inputs**: `custom_prompt` (Message), `input_text` (Message), `message` (Message)

### Smart Transform (`Smart Transform`)
Uses an LLM to generate a function for filtering or transforming structured data and messages.
- **Inputs**: `data` (Data/DataFrame/Message), `filter_instruction` (Message)
- **Outputs**: `data_output` (Data), `dataframe_output` (DataFrame), `message_output` (Message)

### Structured Output (`StructuredOutput`)
Uses an LLM to generate structured data. Ideal for extraction and consistency.
- **Inputs**: `input_value` (Message), `schema_name` (Message), `system_prompt` (Message)
- **Outputs**: `structured_output` (Data), `dataframe_output` (DataFrame)

## lmstudio

### LM Studio (`LMStudioModel`)
Generate text using LM Studio Local LLMs.
- **Inputs**: `input_value` (Message), `system_message` (Message)
- **Outputs**: `text_output` (Message), `model_output` (LanguageModel)

### LM Studio Embeddings (`LMStudioEmbeddingsComponent`)
Generate embeddings using LM Studio.
- **Inputs**: `base_url` (Message)
- **Outputs**: `embeddings` (Embeddings)

## maritalk

### MariTalk (`Maritalk`)
Generates text using MariTalk LLMs.
- **Inputs**: `input_value` (Message), `system_message` (Message)
- **Outputs**: `text_output` (Message), `model_output` (LanguageModel)

## mem0

### Mem0 Chat Memory (`mem0_chat_memory`)
Retrieves and stores chat messages using Mem0 memory storage.
- **Inputs**: `existing_memory` (Memory), `ingest_message` (Message), `mem0_config` (Data), `search_query` (Message), `user_id` (Message)
- **Outputs**: `memory` (Memory), `search_results` (Data)

## milvus

### Milvus (`Milvus`)
Milvus vector store with search capabilities
- **Inputs**: `embedding` (Embeddings), `ingest_data` (Data/DataFrame), `search_query` (Message)
- **Outputs**: `search_results` (Data), `dataframe` (DataFrame)

## mistral

### MistralAI (`MistralModel`)
Generates text using MistralAI LLMs.
- **Inputs**: `input_value` (Message), `system_message` (Message)
- **Outputs**: `text_output` (Message), `model_output` (LanguageModel)

### MistralAI Embeddings (`MistalAIEmbeddings`)
Generate embeddings using MistralAI models.
- **Inputs**: `endpoint` (Message)
- **Outputs**: `embeddings` (Embeddings)

## models_and_agents

### Agent (`Agent`)
Define the agent's instructions, then enter a task to complete using tools.
- **Inputs**: `agent_description` (Message), `context_id` (Message), `format_instructions` (Message), `input_value` (Message), `system_prompt` (Message), `tools` (Tool)
- **Outputs**: `response` (Message)

### Embedding Model (`EmbeddingModel`)
Generate embeddings using a specified provider.
- **Inputs**: `api_base` (Message), `model` (Embeddings), `project_id` (Message)
- **Outputs**: `embeddings` (Embeddings)

### Language Model (`LanguageModelComponent`)
Runs a language model given a specified provider.
- **Inputs**: `input_value` (Message), `ollama_base_url` (Message), `system_message` (Message)
- **Outputs**: `text_output` (Message), `model_output` (LanguageModel)

### MCP Tools (`MCPTools`)
Connect to an MCP server to use its tools.
- **Inputs**: `tool_placeholder` (Message)
- **Outputs**: `response` (DataFrame)

### Message History (`Memory`)
Stores or retrieves stored chat messages from Langflow tables or an external memory.
- **Inputs**: `context_id` (Message), `memory` (Memory), `message` (Message), `sender` (Message), `session_id` (Message)
- **Outputs**: `messages_text` (Message), `dataframe` (DataFrame)

### Prompt Template (`Prompt Template`)
Create a prompt template with dynamic variables.
- **Inputs**: `tool_placeholder` (Message)
- **Outputs**: `prompt` (Message)

## mongodb

### MongoDB Atlas (`MongoDBAtlasVector`)
MongoDB Atlas Vector Store with search capabilities
- **Inputs**: `embedding` (Embeddings), `ingest_data` (Data/DataFrame), `search_query` (Message)
- **Outputs**: `search_results` (Data), `dataframe` (DataFrame)

## needle

### Needle Retriever (`needle`)
A retriever that uses the Needle API to search collections.
- **Inputs**: `collection_id` (Message), `query` (Message)
- **Outputs**: `result` (Message)

## notdiamond

### Not Diamond Router (`NotDiamond`)
Call the right model at the right time with the world's most powerful AI model router.
- **Inputs**: `input_value` (Message), `models` (LanguageModel), `system_message` (Message)
- **Outputs**: `output` (Message), `selected_model` (Text)

## novita

### Novita AI (`NovitaModel`)
Generates text using Novita AI LLMs (OpenAI compatible).
- **Inputs**: `input_value` (Message), `output_parser` (OutputParser), `system_message` (Message)
- **Outputs**: `text_output` (Message), `model_output` (LanguageModel)

## nvidia

### NVIDIA (`NVIDIAModelComponent`)
Generates text using NVIDIA LLMs.
- **Inputs**: `base_url` (Message), `input_value` (Message), `system_message` (Message)
- **Outputs**: `text_output` (Message), `model_output` (LanguageModel)

### NVIDIA Embeddings (`NVIDIAEmbeddingsComponent`)
Generate embeddings using NVIDIA models.
- **Inputs**: `base_url` (Message)
- **Outputs**: `embeddings` (Embeddings)

### NVIDIA Rerank (`NvidiaRerankComponent`)
Rerank documents using the NVIDIA API.
- **Inputs**: `search_query` (Message), `search_results` (Data)
- **Outputs**: `reranked_documents` (Data)

### NVIDIA Retriever Extraction (`NvidiaIngestComponent`)
Multi-modal data extraction from documents using NVIDIA's NeMo API.
- **Inputs**: `base_url` (Message), `file_path` (Data/Message)
- **Outputs**: `dataframe` (DataFrame)

### NVIDIA System-Assist (`NvidiaSystemAssistComponent`)
(Windows only) Prompts NVIDIA System-Assist to interact with the NVIDIA GPU Driver. The user may query GPU specifications, state, and ask the NV-API to perform several GPU-editing acations. The prompt must be human-readable language.
- **Inputs**: `prompt` (Message)
- **Outputs**: `response` (Message)

## olivya

### Place Call (`OlivyaComponent`)
A component to create an outbound call request from Olivya's platform.
- **Inputs**: `api_key` (Message), `conversation_history` (Message), `first_message` (Message), `from_number` (Message), `system_prompt` (Message), `to_number` (Message)
- **Outputs**: `output` (Data)

## ollama

### Ollama (`OllamaModel`)
Generate text using Ollama Local LLMs.
- **Inputs**: `base_url` (Message), `input_value` (Message), `stop_tokens` (Message), `system` (Message), `system_message` (Message), `tags` (Message)
- **Outputs**: `text_output` (Message), `model_output` (LanguageModel), `data_output` (Data), `dataframe_output` (DataFrame)

### Ollama Embeddings (`OllamaEmbeddings`)
Generate embeddings using Ollama models.
- **Inputs**: `base_url` (Message)
- **Outputs**: `embeddings` (Embeddings)

## openai

### OpenAI (`OpenAIModel`)
Generates text using OpenAI LLMs.
- **Inputs**: `input_value` (Message), `system_message` (Message)
- **Outputs**: `text_output` (Message), `model_output` (LanguageModel)

### OpenAI Embeddings (`OpenAIEmbeddings`)
Generate embeddings using OpenAI models.
- **Inputs**: `client` (Message), `deployment` (Message), `openai_api_base` (Message), `openai_api_type` (Message), `openai_api_version` (Message), `openai_organization` (Message)
- **Outputs**: `embeddings` (Embeddings)

## openrouter

### OpenRouter (`OpenRouterComponent`)
OpenRouter provides unified access to multiple AI models from different providers through a single API.
- **Inputs**: `input_value` (Message), `system_message` (Message)
- **Outputs**: `text_output` (Message), `model_output` (LanguageModel)

## perplexity

### Perplexity (`PerplexityModel`)
Generate text using Perplexity LLMs.
- **Inputs**: `input_value` (Message), `system_message` (Message)
- **Outputs**: `text_output` (Message), `model_output` (LanguageModel)

## pgvector

### PGVector (`pgvector`)
PGVector Vector Store with search capabilities
- **Inputs**: `embedding` (Embeddings), `ingest_data` (Data/DataFrame), `search_query` (Message)
- **Outputs**: `search_results` (Data), `dataframe` (DataFrame)

## pinecone

### Pinecone (`Pinecone`)
Pinecone Vector Store with search capabilities
- **Inputs**: `embedding` (Embeddings), `ingest_data` (Data/DataFrame), `search_query` (Message)
- **Outputs**: `search_results` (Data), `dataframe` (DataFrame)

## processing

### Alter Metadata (`AlterMetadata`)
Adds/Removes Metadata Dictionary on inputs
- **Inputs**: `input_value` (Message/Data), `metadata` (Data), `remove_fields` (Message)
- **Outputs**: `data` (Data), `dataframe` (DataFrame)

### Combine Data (`MergeDataComponent`)
Combines data using different operations
- **Inputs**: `data_inputs` (Data)
- **Outputs**: `combined_data` (DataFrame)

### Combine Inputs (`CombineInputs`)
Define custom inputs and combine them into a single output.
- **Outputs**: `data_output` (Data)

### Combine Text (`CombineText`)
Concatenate two text sources into a single text chunk using a specified delimiter.
- **Inputs**: `delimiter` (Message), `text1` (Message), `text2` (Message)
- **Outputs**: `combined_text` (Message)

### Create Data (`CreateData`)
Dynamically create a Data with a specified number of fields.
- **Inputs**: `text_key` (Message)
- **Outputs**: `data` (Data)

### Create List (`CreateList`)
Creates a list of texts.
- **Inputs**: `texts` (str)
- **Outputs**: `list` (Data), `dataframe` (DataFrame)

### Data Operations (`DataOperations`)
Perform various operations on a Data object.
- **Inputs**: `data` (Data), `filter_key` (Message), `mapped_json_display` (Message), `query` (Message), `remove_keys_input` (Message), `select_keys_input` (Message)
- **Outputs**: `data_output` (Data)

### Data to Message (`ParseData`)
Convert Data objects into Messages using any {field_name} from input data.
- **Inputs**: `data` (Data), `template` (Message)
- **Outputs**: `text` (Message), `data_list` (Data)

### Data → DataFrame (`DataToDataFrame`)
Converts one or multiple Data objects into a DataFrame. Each Data object corresponds to one row. Fields from `.data` become columns, and the `.text` (if present) is placed in a 'text' column.
- **Inputs**: `data_list` (Data)
- **Outputs**: `dataframe` (DataFrame)

### DataFrame Operations (`DataFrameOperations`)
Perform various operations on a DataFrame.
- **Inputs**: `df` (DataFrame), `filter_value` (Message), `new_column_value` (Message), `replace_value` (Message), `replacement_value` (Message)
- **Outputs**: `output` (DataFrame)

### Extract Key (`ExtractaKey`)
Extract a specific key from a Data object or a list of Data objects and return the extracted value(s) as Data object(s).
- **Inputs**: `data_input` (Data)
- **Outputs**: `extracted_data` (Data)

### Filter Data (`FilterData`)
Filters a Data object based on a list of keys.
- **Inputs**: `data` (Data), `filter_criteria` (Message)
- **Outputs**: `filtered_data` (Data)

### Filter Values (`FilterDataValues`)
Filter a list of data items based on a specified key, filter value, and comparison operator. Check advanced options to select match comparision.
- **Inputs**: `filter_key` (Data), `filter_value` (Data), `input_data` (Data)
- **Outputs**: `filtered_data` (Data)

### JSON Cleaner (`JSONCleaner`)
Cleans the messy and sometimes incorrect JSON strings produced by LLMs so that they are fully compliant with the JSON spec.
- **Inputs**: `json_str` (Message)
- **Outputs**: `output` (Message)

### Message Store (`StoreMessage`)
Stores a chat message or text into Langflow tables or an external memory.
- **Inputs**: `memory` (Memory), `message` (Message), `sender` (Message), `sender_name` (Message), `session_id` (Message)
- **Outputs**: `stored_messages` (Message)

### Message to Data (`MessagetoData`)
Convert a Message object to a Data object
- **Inputs**: `message` (Message)
- **Outputs**: `data` (Data)

### Output Parser (`OutputParser`)
Transforms the output of an LLM into a specified format.
- **Inputs**: `parser_type` (str)
- **Outputs**: `format_instructions` (Message), `output_parser` (OutputParser)

### Parse DataFrame (`ParseDataFrame`)
Convert a DataFrame into plain text following a specified template. Each column in the DataFrame is treated as a possible template key, e.g. {col_name}.
- **Inputs**: `df` (DataFrame), `template` (Message)
- **Outputs**: `text` (Message)

### Parse JSON (`ParseJSONData`)
Convert and extract JSON fields.
- **Inputs**: `input_value` (Message/Data), `query` (Message)
- **Outputs**: `filtered_data` (Data)

### Parser (`ParserComponent`)
Extracts text using a template.
- **Inputs**: `input_data` (DataFrame/Data), `pattern` (Message), `sep` (Message)
- **Outputs**: `parsed_text` (Message)

### Progress Test (`ProgressTest`)
Test component that simulates a long-running task with progress.
- **Inputs**: `delay_ms` (int), `num_steps` (int)
- **Outputs**: `result` (Data)

### Regex Extractor (`RegexExtractorComponent`)
Extract patterns from text using regular expressions.
- **Inputs**: `input_text` (Message), `pattern` (Message)
- **Outputs**: `data` (Data), `text` (Message)

### Select Data (`SelectData`)
Select a single data from a list of data.
- **Inputs**: `data_list` (Data)
- **Outputs**: `selected_data` (Data)

### Split Text (`SplitText`)
Split text into chunks based on specified criteria.
- **Inputs**: `data_inputs` (Data/DataFrame/Message), `separator` (Message), `text_key` (Message)
- **Outputs**: `dataframe` (DataFrame)

### Text Operations (`TextOperations`)
Perform various text processing operations including text-to-DataFrame conversion.
- **Inputs**: `text_input` (Message), `text_input_2` (Message)

### Type Convert (`TypeConverterComponent`)
Convert between different types (Message, Data, DataFrame)
- **Inputs**: `input_data` (Message/Data/DataFrame)
- **Outputs**: `message_output` (Message)

### Update Data (`UpdateData`)
Dynamically update or append data with the specified fields.
- **Inputs**: `old_data` (Data), `text_key` (Message)
- **Outputs**: `data` (Data)

## prototypes

### Python Function (`PythonFunction`)
Define and execute a Python function that returns a Data object or a Message.
- **Outputs**: `function_output` (Callable), `function_output_data` (Data), `function_output_str` (Message)

## qdrant

### Qdrant (`QdrantVectorStoreComponent`)
Qdrant Vector Store with search capabilities
- **Inputs**: `embedding` (Embeddings), `ingest_data` (Data/DataFrame), `search_query` (Message)
- **Outputs**: `search_results` (Data), `dataframe` (DataFrame)

## redis

### Redis (`Redis`)
Implementation of Vector Store using Redis
- **Inputs**: `embedding` (Embeddings), `ingest_data` (Data/DataFrame), `search_query` (Message)
- **Outputs**: `search_results` (Data), `dataframe` (DataFrame)

### Redis Chat Memory (`RedisChatMemory`)
Retrieves and store chat messages from Redis.
- **Inputs**: `session_id` (Message), `username` (Message)
- **Outputs**: `memory` (Memory)

## sambanova

### SambaNova (`SambaNovaModel`)
Generate text using Sambanova LLMs.
- **Inputs**: `input_value` (Message), `system_message` (Message)
- **Outputs**: `text_output` (Message), `model_output` (LanguageModel)

## scrapegraph

### ScrapeGraph Markdownify API (`ScrapeGraphMarkdownifyApi`)
Given a URL, it will return the markdownified content of the website.
- **Inputs**: `url` (Message)
- **Outputs**: `data` (Data)

### ScrapeGraph Search API (`ScrapeGraphSearchApi`)
Given a search prompt, it will return search results using ScrapeGraph's search functionality.
- **Inputs**: `user_prompt` (Message)
- **Outputs**: `data` (Data)

### ScrapeGraph Smart Scraper API (`ScrapeGraphSmartScraperApi`)
Given a URL, it will return the structured data of the website.
- **Inputs**: `prompt` (Message), `url` (Message)
- **Outputs**: `data` (Data)

## searchapi

### SearchApi (`SearchComponent`)
Calls the SearchApi API with result limiting. Supports Google, Bing and DuckDuckGo.
- **Inputs**: `input_value` (Message)
- **Outputs**: `dataframe` (DataFrame)

## serpapi

### Serp Search API (`Serp`)
Call Serp Search API with result limiting
- **Inputs**: `input_value` (Message)
- **Outputs**: `data` (Data), `text` (Message)

## supabase

### Supabase (`SupabaseVectorStore`)
Supabase Vector Store with search capabilities
- **Inputs**: `embedding` (Embeddings), `ingest_data` (Data/DataFrame), `search_query` (Message)
- **Outputs**: `search_results` (Data), `dataframe` (DataFrame)

## tavily

### Tavily Extract API (`TavilyExtractComponent`)
**Tavily Extract** extract raw content from URLs.
- **Inputs**: `urls` (Message)
- **Outputs**: `dataframe` (Data)

### Tavily Search API (`TavilySearchComponent`)
**Tavily Search** is a search engine optimized for LLMs and RAG,         aimed at efficient, quick, and persistent search results.
- **Inputs**: `exclude_domains` (Message), `include_domains` (Message), `query` (Message)
- **Outputs**: `dataframe` (DataFrame)

## tools

### Calculator (`CalculatorTool`)
Perform basic arithmetic operations on a given expression.
- **Inputs**: `expression` (Message)
- **Outputs**: `api_run_model` (Data), `api_build_tool` (Tool)

### Google Search API [DEPRECATED] (`GoogleSearchAPI`)
Call Google Search API.
- **Inputs**: `input_value` (Message)
- **Outputs**: `api_run_model` (Data), `api_build_tool` (Tool)

### Google Serper API [DEPRECATED] (`GoogleSerperAPI`)
Call the Serper.dev Google Search API.
- **Inputs**: `query` (Message)
- **Outputs**: `api_run_model` (Data), `api_build_tool` (Tool)

### Python Code Structured (`PythonCodeStructuredTool`)
structuredtool dataclass code to tool
- **Inputs**: `global_variables` (Data), `tool_code` (Message), `tool_description` (Message), `tool_name` (Message)
- **Outputs**: `result_tool` (Tool)

### Python REPL (`PythonREPLTool`)
A tool for running Python code in a REPL environment.
- **Inputs**: `description` (str), `global_imports` (str), `name` (str)
- **Outputs**: `api_run_model` (Data), `api_build_tool` (Tool)

### SearXNG Search (`SearXNGTool`)
A component that searches for tools using SearXNG.
- **Inputs**: `url` (Message)
- **Outputs**: `result_tool` (Tool)

### Search API (`SearchAPI`)
Call the searchapi.io API with result limiting
- **Inputs**: `engine` (Message), `input_value` (Message)
- **Outputs**: `api_run_model` (Data), `api_build_tool` (Tool)

### Serp Search API (`SerpAPI`)
Call Serp Search API with result limiting
- **Inputs**: `input_value` (Message)
- **Outputs**: `api_run_model` (Data), `api_build_tool` (Tool)

### Tavily Search API (`TavilyAISearch`)
**Tavily Search API** is a search engine optimized for LLMs and RAG,         aimed at efficient, quick, and persistent search results. It can be used independently or as an agent tool.

Note: Check 'Advanced' for all options.

- **Inputs**: `exclude_domains` (Message), `include_domains` (Message), `query` (Message)
- **Outputs**: `api_run_model` (Data), `api_build_tool` (Tool)

### Wikidata API (`WikidataAPI`)
Performs a search using the Wikidata API.
- **Inputs**: `query` (Message)
- **Outputs**: `api_run_model` (Data), `api_build_tool` (Tool)

### Wikipedia API (`WikipediaAPI`)
Call Wikipedia API.
- **Inputs**: `input_value` (Message), `lang` (Message)
- **Outputs**: `api_run_model` (Data), `api_build_tool` (Tool)

### Yahoo! Finance (`YahooFinanceTool`)
Uses [yfinance](https://pypi.org/project/yfinance/) (unofficial package) to access financial data and market information from Yahoo! Finance.
- **Inputs**: `symbol` (Message)
- **Outputs**: `api_run_model` (Data), `api_build_tool` (Tool)

## twelvelabs

### Convert Astra DB to Pegasus Input (`ConvertAstraToTwelveLabs`)
Converts Astra DB search results to inputs compatible with TwelveLabs Pegasus.
- **Inputs**: `astra_results` (Data)
- **Outputs**: `index_id` (Message), `video_id` (Message)

### Split Video (`SplitVideo`)
Split a video into multiple clips of specified duration.
- **Inputs**: `videodata` (Data)
- **Outputs**: `clips` (Data)

### TwelveLabs Pegasus (`TwelveLabsPegasus`)
Chat with videos using TwelveLabs Pegasus API.
- **Inputs**: `index_id` (Message), `index_name` (Message), `message` (Message), `video_id` (Message), `videodata` (Data)
- **Outputs**: `response` (Message), `processed_video_id` (Message)

### TwelveLabs Pegasus Index Video (`TwelveLabsPegasusIndexVideo`)
Index videos using TwelveLabs and add the video_id to metadata.
- **Inputs**: `videodata` (Data)
- **Outputs**: `indexed_data` (Data)

### TwelveLabs Text Embeddings (`TwelveLabsTextEmbeddings`)
Generate embeddings using TwelveLabs text embedding models.
- **Inputs**: `api_key` (str), `max_retries` (int), `model` (str)
- **Outputs**: `embeddings` (Embeddings)

### TwelveLabs Video Embeddings (`TwelveLabsVideoEmbeddings`)
Generate embeddings from videos using TwelveLabs video embedding models.
- **Inputs**: `api_key` (str), `model_name` (str), `request_timeout` (int)
- **Outputs**: `embeddings` (Embeddings)

### Video File (`VideoFile`)
Load a video file in common video formats.
- **Outputs**: `dataframe` (DataFrame)

## unstructured

### Unstructured API (`Unstructured`)
Uses Unstructured.io API to extract clean text from raw source documents. Supports a wide range of file types.
- **Inputs**: `api_url` (Message), `file_path` (Data/Message)
- **Outputs**: `dataframe` (DataFrame)

## upstash

### Upstash (`Upstash`)
Upstash Vector Store with search capabilities
- **Inputs**: `embedding` (Embeddings), `ingest_data` (Data/DataFrame), `metadata_filter` (Message), `search_query` (Message)
- **Outputs**: `search_results` (Data), `dataframe` (DataFrame)

## utilities

### Calculator (`CalculatorComponent`)
Perform basic arithmetic operations on a given expression.
- **Inputs**: `expression` (Message)
- **Outputs**: `result` (Data)

### Current Date (`CurrentDate`)
Returns the current date and time in the selected timezone.
- **Inputs**: `timezone` (str)
- **Outputs**: `current_date` (Message)

### ID Generator (`IDGenerator`)
Generates a unique ID.
- **Inputs**: `unique_id` (Message)
- **Outputs**: `id` (Message)

### Python Interpreter (`PythonREPLComponent`)
Run Python code with optional imports. Use print() to see the output.
- **Inputs**: `python_code` (Message)
- **Outputs**: `results` (Data)

## vectara

### Vectara (`Vectara`)
Vectara Vector Store with search capabilities
- **Inputs**: `embedding` (Embeddings), `ingest_data` (Data/DataFrame), `search_query` (Message)
- **Outputs**: `search_results` (Data), `dataframe` (DataFrame)

### Vectara RAG (`VectaraRAG`)
Vectara's full end to end RAG
- **Inputs**: `filter` (Message), `search_query` (Message)
- **Outputs**: `answer` (Message)

## vectorstores

### Local DB (`LocalDB`)
Local Vector Store with search capabilities
- **Inputs**: `collection_name` (Message), `embedding` (Embeddings), `ingest_data` (Data/DataFrame), `persist_directory` (Message), `search_query` (Message)
- **Outputs**: `dataframe` (DataFrame)

## vertexai

### Vertex AI (`VertexAiModel`)
Generate text using Vertex AI LLMs.
- **Inputs**: `input_value` (Message), `model_name` (Message), `system_message` (Message)
- **Outputs**: `text_output` (Message), `model_output` (LanguageModel)

### Vertex AI Embeddings (`VertexAIEmbeddings`)
Generate embeddings using Google Cloud Vertex AI models.
- **Inputs**: `location` (Message), `model_name` (Message), `project` (Message), `stop_sequences` (Message)
- **Outputs**: `embeddings` (Embeddings)

## vllm

### vLLM (`vLLMModel`)
Generates text using vLLM models via OpenAI-compatible API.
- **Inputs**: `input_value` (Message), `system_message` (Message)
- **Outputs**: `text_output` (Message), `model_output` (LanguageModel)

### vLLM Embeddings (`vLLMEmbeddings`)
Generate embeddings using vLLM models via OpenAI-compatible API.
- **Inputs**: `api_base` (Message), `model_name` (Message)
- **Outputs**: `embeddings` (Embeddings)

## vlmrun

### VLM Run Transcription (`VLMRunTranscription`)
Extract structured data from audio and video using [VLM Run AI](https://app.vlm.run)
- **Inputs**: `media_url` (Message)
- **Outputs**: `result` (Data)

## weaviate

### Weaviate (`Weaviate`)
Weaviate Vector Store with search capabilities
- **Inputs**: `embedding` (Embeddings), `ingest_data` (Data/DataFrame), `search_query` (Message)
- **Outputs**: `search_results` (Data), `dataframe` (DataFrame)

## wikipedia

### Wikidata (`WikidataComponent`)
Performs a search using the Wikidata API.
- **Inputs**: `query` (Message)
- **Outputs**: `dataframe` (DataFrame)

### Wikipedia (`WikipediaComponent`)
Call Wikipedia API.
- **Inputs**: `input_value` (Message), `lang` (Message)
- **Outputs**: `dataframe` (DataFrame)

## wolframalpha

### WolframAlpha API (`WolframAlphaAPI`)
Enables queries to WolframAlpha for computational data, facts, and calculations across various topics, delivering structured responses.
- **Inputs**: `input_value` (Message)
- **Outputs**: `dataframe` (DataFrame)

## xai

### xAI (`xAIModel`)
Generates text using xAI models like Grok.
- **Inputs**: `base_url` (Message), `input_value` (Message), `system_message` (Message)
- **Outputs**: `text_output` (Message), `model_output` (LanguageModel)

## yahoosearch

### Yahoo! Finance (`YfinanceComponent`)
Uses [yfinance](https://pypi.org/project/yfinance/) (unofficial package) to access financial data and market information from Yahoo! Finance.
- **Inputs**: `symbol` (Message)
- **Outputs**: `dataframe` (DataFrame)

## youtube

### YouTube Channel (`YouTubeChannelComponent`)
Retrieves detailed information and statistics about YouTube channels as a DataFrame.
- **Inputs**: `channel_url` (Message)
- **Outputs**: `channel_df` (DataFrame)

### YouTube Comments (`YouTubeCommentsComponent`)
Retrieves and analyzes comments from YouTube videos.
- **Inputs**: `video_url` (Message)
- **Outputs**: `comments` (DataFrame)

### YouTube Playlist (`YouTubePlaylistComponent`)
Extracts all video URLs from a YouTube playlist.
- **Inputs**: `playlist_url` (Message)
- **Outputs**: `video_urls` (DataFrame)

### YouTube Search (`YouTubeSearchComponent`)
Searches YouTube videos based on query.
- **Inputs**: `query` (Message)
- **Outputs**: `results` (DataFrame)

### YouTube Transcripts (`YouTubeTranscripts`)
Extracts spoken content from YouTube videos with multiple output options.
- **Inputs**: `url` (Message)
- **Outputs**: `dataframe` (DataFrame), `message` (Message), `data_output` (Data)

### YouTube Trending (`YouTubeTrendingComponent`)
Retrieves trending videos from YouTube with filtering options.
- **Inputs**: `api_key` (str), `category` (str), `include_content_details` (bool)
- **Outputs**: `trending_videos` (DataFrame)

### YouTube Video Details (`YouTubeVideoDetailsComponent`)
Retrieves detailed information and statistics about YouTube videos.
- **Inputs**: `video_url` (Message)
- **Outputs**: `video_data` (DataFrame)

## zep

### Zep Chat Memory (`ZepChatMemory`)
Retrieves and store chat messages from Zep.
- **Inputs**: `session_id` (Message), `url` (Message)
- **Outputs**: `memory` (Memory)
