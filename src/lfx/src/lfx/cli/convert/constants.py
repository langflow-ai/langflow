"""Constants for JSON to Python flow conversion."""

from __future__ import annotations

# ============================================================================
# Component Import Mappings
# ============================================================================
# Maps Langflow component types to their Python import paths in LFX.

COMPONENT_IMPORTS: dict[str, str] = {
    # =========================================================================
    # Input/Output
    # =========================================================================
    "ChatInput": "lfx.components.input_output.ChatInput",
    "ChatOutput": "lfx.components.input_output.ChatOutput",
    "TextInputComponent": "lfx.components.input_output.TextInputComponent",
    "TextInput": "lfx.components.input_output.TextInputComponent",
    "TextOutputComponent": "lfx.components.input_output.TextOutputComponent",
    "TextOutput": "lfx.components.input_output.TextOutputComponent",
    "WebhookComponent": "lfx.components.input_output.WebhookComponent",
    "Webhook": "lfx.components.input_output.WebhookComponent",
    # =========================================================================
    # Models and Agents
    # =========================================================================
    "Agent": "lfx.components.models_and_agents.AgentComponent",
    "AgentComponent": "lfx.components.models_and_agents.AgentComponent",
    "PromptComponent": "lfx.components.models_and_agents.PromptComponent",
    "Prompt": "lfx.components.models_and_agents.PromptComponent",
    "LanguageModelComponent": "lfx.components.models_and_agents.LanguageModelComponent",
    "LanguageModel": "lfx.components.models_and_agents.LanguageModelComponent",
    "MemoryComponent": "lfx.components.models_and_agents.MemoryComponent",
    "Memory": "lfx.components.models_and_agents.MemoryComponent",
    "EmbeddingModelComponent": "lfx.components.models_and_agents.EmbeddingModelComponent",
    "EmbeddingModel": "lfx.components.models_and_agents.EmbeddingModelComponent",
    "MCPToolsComponent": "lfx.components.models_and_agents.MCPToolsComponent",
    # =========================================================================
    # LLM Providers - OpenAI
    # =========================================================================
    "OpenAIModel": "lfx.components.openai.OpenAIModelComponent",
    "OpenAIModelComponent": "lfx.components.openai.OpenAIModelComponent",
    "OpenAIChatModel": "lfx.components.openai.OpenAIChatModelComponent",
    "OpenAIEmbeddings": "lfx.components.openai.OpenAIEmbeddingsComponent",
    # =========================================================================
    # LLM Providers - Anthropic
    # =========================================================================
    "AnthropicModel": "lfx.components.anthropic.AnthropicModelComponent",
    "AnthropicModelComponent": "lfx.components.anthropic.AnthropicModelComponent",
    # =========================================================================
    # LLM Providers - Google
    # =========================================================================
    "GoogleGenerativeAIComponent": "lfx.components.google.GoogleGenerativeAIComponent",
    "GoogleGenerativeAI": "lfx.components.google.GoogleGenerativeAIComponent",
    "ChatVertexAI": "lfx.components.google.ChatVertexAIComponent",
    "ChatVertexAIComponent": "lfx.components.google.ChatVertexAIComponent",
    "VertexAIEmbeddings": "lfx.components.google.VertexAIEmbeddingsComponent",
    # =========================================================================
    # LLM Providers - Groq
    # =========================================================================
    "GroqModel": "lfx.components.groq.GroqModelComponent",
    "GroqModelComponent": "lfx.components.groq.GroqModelComponent",
    # =========================================================================
    # LLM Providers - Ollama
    # =========================================================================
    "OllamaModel": "lfx.components.ollama.ChatOllamaComponent",
    "ChatOllama": "lfx.components.ollama.ChatOllamaComponent",
    "ChatOllamaComponent": "lfx.components.ollama.ChatOllamaComponent",
    "OllamaEmbeddings": "lfx.components.ollama.OllamaEmbeddingsComponent",
    # =========================================================================
    # LLM Providers - Azure
    # =========================================================================
    "AzureChatOpenAI": "lfx.components.azure.AzureChatOpenAIComponent",
    "AzureChatOpenAIComponent": "lfx.components.azure.AzureChatOpenAIComponent",
    "AzureOpenAIEmbeddings": "lfx.components.azure.AzureOpenAIEmbeddingsComponent",
    # =========================================================================
    # LLM Providers - Amazon Bedrock
    # =========================================================================
    "AmazonBedrock": "lfx.components.amazon.AmazonBedrockComponent",
    "AmazonBedrockComponent": "lfx.components.amazon.AmazonBedrockComponent",
    "AmazonBedrockEmbeddings": "lfx.components.amazon.AmazonBedrockEmbeddingsComponent",
    # =========================================================================
    # LLM Providers - Mistral
    # =========================================================================
    "MistralModel": "lfx.components.mistral.MistralModelComponent",
    "MistralModelComponent": "lfx.components.mistral.MistralModelComponent",
    "MistralEmbeddings": "lfx.components.mistral.MistralEmbeddingsComponent",
    # =========================================================================
    # LLM Providers - Cohere
    # =========================================================================
    "CohereModel": "lfx.components.cohere.CohereComponent",
    "CohereComponent": "lfx.components.cohere.CohereComponent",
    "CohereEmbeddings": "lfx.components.cohere.CohereEmbeddingsComponent",
    "CohereRerank": "lfx.components.cohere.CohereRerankComponent",
    # =========================================================================
    # LLM Providers - HuggingFace
    # =========================================================================
    "HuggingFaceModel": "lfx.components.huggingface.HuggingFaceComponent",
    "HuggingFaceComponent": "lfx.components.huggingface.HuggingFaceComponent",
    "HuggingFaceInferenceAPI": "lfx.components.huggingface.HuggingFaceInferenceAPIComponent",
    # =========================================================================
    # LLM Providers - NVIDIA
    # =========================================================================
    "NVIDIAModel": "lfx.components.nvidia.NVIDIAModelComponent",
    "NVIDIAModelComponent": "lfx.components.nvidia.NVIDIAModelComponent",
    "NVIDIAEmbeddings": "lfx.components.nvidia.NVIDIAEmbeddingsComponent",
    "NVIDIARerank": "lfx.components.nvidia.NVIDIARerankComponent",
    # =========================================================================
    # LLM Providers - IBM Watson
    # =========================================================================
    "WatsonxAI": "lfx.components.ibm.WatsonxAIComponent",
    "WatsonxAIComponent": "lfx.components.ibm.WatsonxAIComponent",
    "WatsonxEmbeddings": "lfx.components.ibm.WatsonxEmbeddingsComponent",
    # =========================================================================
    # LLM Providers - DeepSeek
    # =========================================================================
    "DeepSeekModel": "lfx.components.deepseek.DeepSeekModelComponent",
    "DeepSeekModelComponent": "lfx.components.deepseek.DeepSeekModelComponent",
    # =========================================================================
    # LLM Providers - xAI
    # =========================================================================
    "XAIModel": "lfx.components.xai.XAIModelComponent",
    "XAIModelComponent": "lfx.components.xai.XAIModelComponent",
    # =========================================================================
    # Data Source
    # =========================================================================
    "URLComponent": "lfx.components.data_source.URLComponent",
    "URL": "lfx.components.data_source.URLComponent",
    "WebSearchComponent": "lfx.components.data_source.WebSearchComponent",
    "WebSearch": "lfx.components.data_source.WebSearchComponent",
    "UnifiedWebSearch": "lfx.components.data_source.WebSearchComponent",
    "APIRequestComponent": "lfx.components.data_source.APIRequestComponent",
    "APIRequest": "lfx.components.data_source.APIRequestComponent",
    "CSVToDataComponent": "lfx.components.data_source.CSVToDataComponent",
    "CSVToData": "lfx.components.data_source.CSVToDataComponent",
    "JSONToDataComponent": "lfx.components.data_source.JSONToDataComponent",
    "JSONToData": "lfx.components.data_source.JSONToDataComponent",
    "SQLComponent": "lfx.components.data_source.SQLComponent",
    "SQL": "lfx.components.data_source.SQLComponent",
    "RSSReaderComponent": "lfx.components.data_source.RSSReaderComponent",
    "RSSReader": "lfx.components.data_source.RSSReaderComponent",
    "NewsSearchComponent": "lfx.components.data_source.NewsSearchComponent",
    "NewsSearch": "lfx.components.data_source.NewsSearchComponent",
    # =========================================================================
    # Files and Knowledge
    # =========================================================================
    "Directory": "lfx.components.files_and_knowledge.DirectoryComponent",
    "DirectoryComponent": "lfx.components.files_and_knowledge.DirectoryComponent",
    "File": "lfx.components.files_and_knowledge.FileComponent",
    "FileComponent": "lfx.components.files_and_knowledge.FileComponent",
    "SaveToFile": "lfx.components.files_and_knowledge.SaveToFileComponent",
    "SaveToFileComponent": "lfx.components.files_and_knowledge.SaveToFileComponent",
    "Ingestion": "lfx.components.files_and_knowledge.IngestionComponent",
    "IngestionComponent": "lfx.components.files_and_knowledge.IngestionComponent",
    "Retrieval": "lfx.components.files_and_knowledge.RetrievalComponent",
    "RetrievalComponent": "lfx.components.files_and_knowledge.RetrievalComponent",
    # =========================================================================
    # Processing / Text Operations
    # =========================================================================
    "CombineTextComponent": "lfx.components.processing.CombineTextComponent",
    "CombineText": "lfx.components.processing.CombineTextComponent",
    "SplitTextComponent": "lfx.components.processing.SplitTextComponent",
    "SplitText": "lfx.components.processing.SplitTextComponent",
    "FilterDataComponent": "lfx.components.processing.FilterDataComponent",
    "FilterData": "lfx.components.processing.FilterDataComponent",
    "ParseDataComponent": "lfx.components.processing.ParseDataComponent",
    "ParseData": "lfx.components.processing.ParseDataComponent",
    "SelectDataComponent": "lfx.components.processing.SelectDataComponent",
    "SelectData": "lfx.components.processing.SelectDataComponent",
    "UpdateDataComponent": "lfx.components.processing.UpdateDataComponent",
    "UpdateData": "lfx.components.processing.UpdateDataComponent",
    "AlterMetadataComponent": "lfx.components.processing.AlterMetadataComponent",
    "AlterMetadata": "lfx.components.processing.AlterMetadataComponent",
    "TypeConverterComponent": "lfx.components.processing.TypeConverterComponent",
    "TypeConverter": "lfx.components.processing.TypeConverterComponent",
    # =========================================================================
    # Text Splitters
    # =========================================================================
    "CharacterTextSplitter": "lfx.components.langchain_utilities.CharacterTextSplitterComponent",
    "CharacterTextSplitterComponent": "lfx.components.langchain_utilities.CharacterTextSplitterComponent",
    "RecursiveCharacterTextSplitter": ("lfx.components.langchain_utilities.RecursiveCharacterTextSplitterComponent"),
    "RecursiveCharacterTextSplitterComponent": (
        "lfx.components.langchain_utilities.RecursiveCharacterTextSplitterComponent"
    ),
    "SemanticTextSplitter": "lfx.components.langchain_utilities.SemanticTextSplitterComponent",
    "SemanticTextSplitterComponent": "lfx.components.langchain_utilities.SemanticTextSplitterComponent",
    # =========================================================================
    # Vector Stores
    # =========================================================================
    "Chroma": "lfx.components.chroma.ChromaVectorStoreComponent",
    "ChromaVectorStore": "lfx.components.chroma.ChromaVectorStoreComponent",
    "ChromaVectorStoreComponent": "lfx.components.chroma.ChromaVectorStoreComponent",
    "FAISS": "lfx.components.FAISS.FAISSVectorStoreComponent",
    "FAISSVectorStore": "lfx.components.FAISS.FAISSVectorStoreComponent",
    "FAISSVectorStoreComponent": "lfx.components.FAISS.FAISSVectorStoreComponent",
    "Pinecone": "lfx.components.pinecone.PineconeVectorStoreComponent",
    "PineconeVectorStore": "lfx.components.pinecone.PineconeVectorStoreComponent",
    "PineconeVectorStoreComponent": "lfx.components.pinecone.PineconeVectorStoreComponent",
    "Qdrant": "lfx.components.qdrant.QdrantVectorStoreComponent",
    "QdrantVectorStore": "lfx.components.qdrant.QdrantVectorStoreComponent",
    "QdrantVectorStoreComponent": "lfx.components.qdrant.QdrantVectorStoreComponent",
    "Weaviate": "lfx.components.weaviate.WeaviateVectorStoreComponent",
    "WeaviateVectorStore": "lfx.components.weaviate.WeaviateVectorStoreComponent",
    "WeaviateVectorStoreComponent": "lfx.components.weaviate.WeaviateVectorStoreComponent",
    "Milvus": "lfx.components.milvus.MilvusVectorStoreComponent",
    "MilvusVectorStore": "lfx.components.milvus.MilvusVectorStoreComponent",
    "MilvusVectorStoreComponent": "lfx.components.milvus.MilvusVectorStoreComponent",
    "AstraDB": "lfx.components.datastax.AstraDBVectorStoreComponent",
    "AstraDBVectorStore": "lfx.components.datastax.AstraDBVectorStoreComponent",
    "AstraDBVectorStoreComponent": "lfx.components.datastax.AstraDBVectorStoreComponent",
    "Cassandra": "lfx.components.cassandra.CassandraVectorStoreComponent",
    "CassandraVectorStore": "lfx.components.cassandra.CassandraVectorStoreComponent",
    "CassandraVectorStoreComponent": "lfx.components.cassandra.CassandraVectorStoreComponent",
    "Elasticsearch": "lfx.components.elastic.ElasticsearchVectorStoreComponent",
    "ElasticsearchVectorStore": "lfx.components.elastic.ElasticsearchVectorStoreComponent",
    "OpenSearch": "lfx.components.elastic.OpenSearchVectorStoreComponent",
    "OpenSearchVectorStore": "lfx.components.elastic.OpenSearchVectorStoreComponent",
    "MongoDB": "lfx.components.mongodb.MongoDBAtlasVectorStoreComponent",
    "MongoDBAtlas": "lfx.components.mongodb.MongoDBAtlasVectorStoreComponent",
    "Supabase": "lfx.components.supabase.SupabaseVectorStoreComponent",
    "SupabaseVectorStore": "lfx.components.supabase.SupabaseVectorStoreComponent",
    "Couchbase": "lfx.components.couchbase.CouchbaseVectorStoreComponent",
    "CouchbaseVectorStore": "lfx.components.couchbase.CouchbaseVectorStoreComponent",
    "Clickhouse": "lfx.components.clickhouse.ClickhouseVectorStoreComponent",
    "ClickhouseVectorStore": "lfx.components.clickhouse.ClickhouseVectorStoreComponent",
    "Upstash": "lfx.components.upstash.UpstashVectorStoreComponent",
    "UpstashVectorStore": "lfx.components.upstash.UpstashVectorStoreComponent",
    # =========================================================================
    # Flow Controls / Logic
    # =========================================================================
    "ConditionalRouter": "lfx.components.flow_controls.ConditionalRouterComponent",
    "ConditionalRouterComponent": "lfx.components.flow_controls.ConditionalRouterComponent",
    "DataConditionalRouter": "lfx.components.flow_controls.DataConditionalRouterComponent",
    "DataConditionalRouterComponent": "lfx.components.flow_controls.DataConditionalRouterComponent",
    "FlowTool": "lfx.components.flow_controls.FlowToolComponent",
    "FlowToolComponent": "lfx.components.flow_controls.FlowToolComponent",
    "Listen": "lfx.components.flow_controls.ListenComponent",
    "ListenComponent": "lfx.components.flow_controls.ListenComponent",
    "Notify": "lfx.components.flow_controls.NotifyComponent",
    "NotifyComponent": "lfx.components.flow_controls.NotifyComponent",
    "Loop": "lfx.components.flow_controls.LoopComponent",
    "LoopComponent": "lfx.components.flow_controls.LoopComponent",
    "PassMessage": "lfx.components.flow_controls.PassMessageComponent",
    "PassMessageComponent": "lfx.components.flow_controls.PassMessageComponent",
    "RunFlow": "lfx.components.flow_controls.RunFlowComponent",
    "RunFlowComponent": "lfx.components.flow_controls.RunFlowComponent",
    "SubFlow": "lfx.components.flow_controls.SubFlowComponent",
    "SubFlowComponent": "lfx.components.flow_controls.SubFlowComponent",
    # =========================================================================
    # LLM Operations
    # =========================================================================
    "BatchRun": "lfx.components.llm_operations.BatchRunComponent",
    "BatchRunComponent": "lfx.components.llm_operations.BatchRunComponent",
    "StructuredOutput": "lfx.components.llm_operations.StructuredOutputComponent",
    "StructuredOutputComponent": "lfx.components.llm_operations.StructuredOutputComponent",
    "LLMConditionalRouter": "lfx.components.llm_operations.LLMConditionalRouterComponent",
    "LLMConditionalRouterComponent": "lfx.components.llm_operations.LLMConditionalRouterComponent",
    # =========================================================================
    # Helpers / Utilities
    # =========================================================================
    "Calculator": "lfx.components.helpers.CalculatorComponent",
    "CalculatorComponent": "lfx.components.helpers.CalculatorComponent",
    "CurrentDate": "lfx.components.helpers.CurrentDateComponent",
    "CurrentDateComponent": "lfx.components.helpers.CurrentDateComponent",
    "IDGenerator": "lfx.components.helpers.IDGeneratorComponent",
    "IDGeneratorComponent": "lfx.components.helpers.IDGeneratorComponent",
    "CreateList": "lfx.components.helpers.CreateListComponent",
    "CreateListComponent": "lfx.components.helpers.CreateListComponent",
    "StoreMessage": "lfx.components.helpers.StoreMessageComponent",
    "StoreMessageComponent": "lfx.components.helpers.StoreMessageComponent",
    "OutputParser": "lfx.components.helpers.OutputParserComponent",
    "OutputParserComponent": "lfx.components.helpers.OutputParserComponent",
    # =========================================================================
    # Search Tools
    # =========================================================================
    "TavilySearch": "lfx.components.tavily.TavilySearchComponent",
    "TavilySearchComponent": "lfx.components.tavily.TavilySearchComponent",
    "TavilySearchTool": "lfx.components.tavily.TavilySearchToolComponent",
    "TavilyExtract": "lfx.components.tavily.TavilyExtractComponent",
    "SerpAPI": "lfx.components.serp.SerpAPIComponent",
    "SerpAPIComponent": "lfx.components.serp.SerpAPIComponent",
    "GoogleSearch": "lfx.components.google.GoogleSearchComponent",
    "GoogleSearchComponent": "lfx.components.google.GoogleSearchComponent",
    "BingSearch": "lfx.components.bing.BingSearchAPIComponent",
    "BingSearchAPIComponent": "lfx.components.bing.BingSearchAPIComponent",
    "DuckDuckGoSearch": "lfx.components.duckduckgo.DuckDuckGoSearchComponent",
    "DuckDuckGoSearchComponent": "lfx.components.duckduckgo.DuckDuckGoSearchComponent",
    "WikipediaSearch": "lfx.components.wikipedia.WikipediaComponent",
    "WikipediaComponent": "lfx.components.wikipedia.WikipediaComponent",
    "ArXiv": "lfx.components.arxiv.ArXivComponent",
    "ArXivComponent": "lfx.components.arxiv.ArXivComponent",
    # =========================================================================
    # Web Scraping / Crawling
    # =========================================================================
    "FirecrawlScrape": "lfx.components.firecrawl.FirecrawlScrapeAPIComponent",
    "FirecrawlScrapeAPIComponent": "lfx.components.firecrawl.FirecrawlScrapeAPIComponent",
    "FirecrawlCrawl": "lfx.components.firecrawl.FirecrawlCrawlAPIComponent",
    "FirecrawlCrawlAPIComponent": "lfx.components.firecrawl.FirecrawlCrawlAPIComponent",
    "FirecrawlMap": "lfx.components.firecrawl.FirecrawlMapAPIComponent",
    "FirecrawlMapAPIComponent": "lfx.components.firecrawl.FirecrawlMapAPIComponent",
    "FirecrawlExtract": "lfx.components.firecrawl.FirecrawlExtractAPIComponent",
    "FirecrawlExtractAPIComponent": "lfx.components.firecrawl.FirecrawlExtractAPIComponent",
    "Spider": "lfx.components.spider.SpiderTool",
    "SpiderTool": "lfx.components.spider.SpiderTool",
    "Apify": "lfx.components.apify.ApifyActorsComponent",
    "ApifyActorsComponent": "lfx.components.apify.ApifyActorsComponent",
    # =========================================================================
    # Document Loaders
    # =========================================================================
    "Unstructured": "lfx.components.unstructured.UnstructuredComponent",
    "UnstructuredComponent": "lfx.components.unstructured.UnstructuredComponent",
    "Confluence": "lfx.components.confluence.ConfluenceComponent",
    "ConfluenceComponent": "lfx.components.confluence.ConfluenceComponent",
    # =========================================================================
    # Langchain Utilities / Agents
    # =========================================================================
    "ToolCallingAgent": "lfx.components.langchain_utilities.ToolCallingAgentComponent",
    "ToolCallingAgentComponent": "lfx.components.langchain_utilities.ToolCallingAgentComponent",
    "CSVAgent": "lfx.components.langchain_utilities.CSVAgentComponent",
    "CSVAgentComponent": "lfx.components.langchain_utilities.CSVAgentComponent",
    "JSONAgent": "lfx.components.langchain_utilities.JSONAgentComponent",
    "JSONAgentComponent": "lfx.components.langchain_utilities.JSONAgentComponent",
    "SQLAgent": "lfx.components.langchain_utilities.SQLAgentComponent",
    "SQLAgentComponent": "lfx.components.langchain_utilities.SQLAgentComponent",
    "XMLAgent": "lfx.components.langchain_utilities.XMLAgentComponent",
    "XMLAgentComponent": "lfx.components.langchain_utilities.XMLAgentComponent",
    "RetrievalQA": "lfx.components.langchain_utilities.RetrievalQAComponent",
    "RetrievalQAComponent": "lfx.components.langchain_utilities.RetrievalQAComponent",
    "SelfQueryRetriever": "lfx.components.langchain_utilities.SelfQueryRetrieverComponent",
    "SelfQueryRetrieverComponent": "lfx.components.langchain_utilities.SelfQueryRetrieverComponent",
    "VectorStoreInfo": "lfx.components.langchain_utilities.VectorStoreInfoComponent",
    "VectorStoreInfoComponent": "lfx.components.langchain_utilities.VectorStoreInfoComponent",
    # =========================================================================
    # CrewAI
    # =========================================================================
    "CrewAIAgent": "lfx.components.crewai.CrewAIAgentComponent",
    "CrewAIAgentComponent": "lfx.components.crewai.CrewAIAgentComponent",
    "SequentialCrew": "lfx.components.crewai.SequentialCrewComponent",
    "SequentialCrewComponent": "lfx.components.crewai.SequentialCrewComponent",
    "HierarchicalCrew": "lfx.components.crewai.HierarchicalCrewComponent",
    "HierarchicalCrewComponent": "lfx.components.crewai.HierarchicalCrewComponent",
    "SequentialTask": "lfx.components.crewai.SequentialTaskComponent",
    "SequentialTaskComponent": "lfx.components.crewai.SequentialTaskComponent",
    "HierarchicalTask": "lfx.components.crewai.HierarchicalTaskComponent",
    "HierarchicalTaskComponent": "lfx.components.crewai.HierarchicalTaskComponent",
    # =========================================================================
    # Notion
    # =========================================================================
    "NotionPageCreator": "lfx.components.Notion.NotionPageCreator",
    "NotionSearch": "lfx.components.Notion.NotionSearch",
    "NotionPageContent": "lfx.components.Notion.NotionPageContent",
    "NotionListPages": "lfx.components.Notion.NotionListPages",
    # =========================================================================
    # YouTube
    # =========================================================================
    "YouTubeTranscripts": "lfx.components.youtube.YouTubeTranscriptsComponent",
    "YouTubeTranscriptsComponent": "lfx.components.youtube.YouTubeTranscriptsComponent",
    "YouTubeSearch": "lfx.components.youtube.YouTubeSearchComponent",
    "YouTubeSearchComponent": "lfx.components.youtube.YouTubeSearchComponent",
    "YouTubeChannel": "lfx.components.youtube.YouTubeChannelComponent",
    "YouTubeChannelComponent": "lfx.components.youtube.YouTubeChannelComponent",
    # =========================================================================
    # Chat Memory
    # =========================================================================
    "ZepChatMemory": "lfx.components.zep.ZepChatMemory",
    "AstraDBChatMemory": "lfx.components.datastax.AstraDBChatMemory",
    "CassandraChatMemory": "lfx.components.cassandra.CassandraChatMemory",
}

# ============================================================================
# Field Filtering Constants
# ============================================================================

SKIP_FIELDS: frozenset[str] = frozenset(
    {
        "code",
        "_type",
        "_frontend_node_flow_id",
        "_frontend_node_folder_id",
        "show",
        "advanced",
        "dynamic",
        "info",
        "display_name",
        "required",
        "placeholder",
        "list",
        "multiline",
        "input_types",
        "output_types",
        "file_path",
        "fileTypes",
        "password",
        "load_from_db",
        "title_case",
        "real_time_refresh",
        "refresh_button",
        "trace_as_input",
        "trace_as_metadata",
        "_input_type",
        "list_add_label",
        "name",
        "type",
        "options",
        "tool_mode",
        "track_in_telemetry",
        "copy_field",
        "ai_enabled",
        "override_skip",
    }
)

LONG_TEXT_FIELDS: frozenset[str] = frozenset(
    {
        "system_prompt",
        "prompt",
        "template",
        "agent_description",
        "format_instructions",
    }
)

MIN_PROMPT_LENGTH = 200

PYTHON_RESERVED_WORDS: frozenset[str] = frozenset(
    {
        "input",
        "output",
        "type",
        "id",
        "class",
        "def",
        "return",
        "if",
        "else",
        "for",
        "while",
    }
)

# ============================================================================
# Output Name to Method Name Mapping
# ============================================================================
# Maps (component_type, output_name) to the actual method name.
# The JSON stores output names in sourceHandle.name, but the Python code needs
# to call the method name for .set() connections to work correctly.
#
# Format: "ComponentType.output_name": "method_name"
# If not found, falls back to using output_name as method_name.

OUTPUT_TO_METHOD: dict[str, str] = {
    # Input/Output
    "ChatInput.message": "message_response",
    "ChatOutput.message": "message_response",
    "TextInputComponent.text": "text_response",
    "TextOutputComponent.text": "text_response",
    # Models and Agents
    "AgentComponent.response": "message_response",
    "Agent.response": "message_response",
    "PromptComponent.prompt": "build_prompt",
    "Prompt.prompt": "build_prompt",
    "LanguageModelComponent.text_output": "text_response",
    "LanguageModel.text_output": "text_response",
    "MemoryComponent.messages": "retrieve_messages",
    "Memory.messages": "retrieve_messages",
    # Data Sources
    "URLComponent.page_results": "fetch_content",
    "URLComponent.raw_results": "fetch_content_as_message",
    "WebSearchComponent.results": "search",
    "DirectoryComponent.dataframe": "as_dataframe",
    "FileComponent.data": "load_file",
    "APIRequest.data": "make_request",
    "AirtableComponent.data": "query_records",
    # Vector Stores
    "AstraDB.search_results": "search_documents",
    "AstraDBComponent.search_results": "search_documents",
    "ChromaComponent.search_results": "search_documents",
    "Chroma.search_results": "search_documents",
    "PineconeComponent.search_results": "search_documents",
    "Pinecone.search_results": "search_documents",
    "QdrantComponent.search_results": "search_documents",
    "Qdrant.search_results": "search_documents",
    "PGVectorComponent.search_results": "search_documents",
    "PGVector.search_results": "search_documents",
    "MilvusComponent.search_results": "search_documents",
    "Milvus.search_results": "search_documents",
    "WeaviateComponent.search_results": "search_documents",
    "Weaviate.search_results": "search_documents",
    "FAISSComponent.search_results": "search_documents",
    "FAISS.search_results": "search_documents",
    # Text Processing
    "SplitText.chunks": "split_text",
    "SplitTextComponent.chunks": "split_text",
    "ParseData.text": "parse_data",
    "ParseDataComponent.text": "parse_data",
    "CombineText.combined": "combine_text",
    "CombineTextComponent.combined": "combine_text",
    "FilterData.filtered": "filter_data",
    "FilterDataComponent.filtered": "filter_data",
    "ReplaceText.text": "replace_text",
    "ExtractKey.output": "extract_key",
    "MergeData.combined": "merge_data",
    "UpdateData.data": "update_data",
    "SelectivePassThrough.output": "select_output",
    "ConditionalRouter.output": "route_message",
    "Notify.output_value": "notify",
    "Listen.output_value": "listen",
    # Helpers
    "CalculatorComponent.result": "calculate",
    "Calculator.result": "calculate",
    "CurrentDateComponent.date": "get_current_date",
    "CurrentDate.date": "get_current_date",
    "IDGeneratorComponent.id": "generate_id",
    "IDGenerator.id": "generate_id",
    "CreateListComponent.list": "create_list",
    "CreateList.list": "create_list",
    "OutputParserComponent.output": "parse_output",
    "OutputParser.output": "parse_output",
}


def get_method_name(node_type: str, output_name: str) -> str:
    """Get the method name for a given component type and output name.

    Args:
        node_type: The component type (e.g., "ChatInput", "AgentComponent")
        output_name: The output name from JSON (e.g., "message", "response")

    Returns:
        The method name to use in generated code. Falls back to output_name
        if no mapping is found.
    """
    # Try exact match first
    key = f"{node_type}.{output_name}"
    if key in OUTPUT_TO_METHOD:
        return OUTPUT_TO_METHOD[key]

    # Fall back to output_name as method_name
    return output_name


# ============================================================================
# Known Input Types for Custom Component Imports
# ============================================================================
# These are the Input types that might be used in custom component code.
# When parsing custom component code, we detect these to generate proper imports.

KNOWN_INPUT_TYPES: frozenset[str] = frozenset(
    {
        "BoolInput",
        "DataInput",
        "DataFrameInput",
        "DictInput",
        "DropdownInput",
        "FileInput",
        "FloatInput",
        "HandleInput",
        "IntInput",
        "LinkInput",
        "MessageInput",
        "MessageTextInput",
        "MultilineInput",
        "MultilineSecretInput",
        "MultiselectInput",
        "NestedDictInput",
        "Output",
        "PromptInput",
        "SecretStrInput",
        "SliderInput",
        "StrInput",
        "TableInput",
    }
)
