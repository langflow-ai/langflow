from typing import Any

OPENAI_MODELS = [
    "text-davinci-003",
    "text-davinci-002",
    "text-curie-001",
    "text-babbage-001",
    "text-ada-001",
]
CHAT_OPENAI_MODELS = [
    "gpt-4o",
    "gpt-4-turbo-preview",
    "gpt-4-0125-preview",
    "gpt-4-1106-preview",
    "gpt-4-vision-preview",
    "gpt-3.5-turbo-0125",
    "gpt-3.5-turbo-1106",
]


ANTHROPIC_MODELS = [
    # largest model, ideal for a wide range of more complex tasks.
    "claude-v1",
    # An enhanced version of claude-v1 with a 100,000 token (roughly 75,000 word) context window.
    "claude-v1-100k",
    # A smaller model with far lower latency, sampling at roughly 40 words/sec!
    "claude-instant-v1",
    # Like claude-instant-v1 with a 100,000 token context window but retains its performance.
    "claude-instant-v1-100k",
    # Specific sub-versions of the above models:
    # Vs claude-v1.2: better instruction-following, code, and non-English dialogue and writing.
    "claude-v1.3",
    # An enhanced version of claude-v1.3 with a 100,000 token (roughly 75,000 word) context window.
    "claude-v1.3-100k",
    # Vs claude-v1.1: small adv in general helpfulness, instruction following, coding, and other tasks.
    "claude-v1.2",
    # An earlier version of claude-v1.
    "claude-v1.0",
    # Latest version of claude-instant-v1. Better than claude-instant-v1.0 at most tasks.
    "claude-instant-v1.1",
    # Version of claude-instant-v1.1 with a 100K token context window.
    "claude-instant-v1.1-100k",
    # An earlier version of claude-instant-v1.
    "claude-instant-v1.0",
]

DEFAULT_PYTHON_FUNCTION = """
def python_function(text: str) -> str:
    \"\"\"This is a default python function that returns the input text\"\"\"
    return text
"""


PYTHON_BASIC_TYPES = [str, bool, int, float, tuple, list, dict, set]
DIRECT_TYPES = ["str", "bool", "dict", "int", "float", "Any", "prompt", "code", "NestedDict", "table"]


LOADERS_INFO: list[dict[str, Any]] = [
    {
        "loader": "AirbyteJSONLoader",
        "name": "Airbyte JSON (.jsonl)",
        "import": "langchain_community.document_loaders.AirbyteJSONLoader",
        "defaultFor": ["jsonl"],
        "allowdTypes": ["jsonl"],
    },
    {
        "loader": "JSONLoader",
        "name": "JSON (.json)",
        "import": "langchain_community.document_loaders.JSONLoader",
        "defaultFor": ["json"],
        "allowdTypes": ["json"],
    },
    {
        "loader": "BSHTMLLoader",
        "name": "BeautifulSoup4 HTML (.html, .htm)",
        "import": "langchain_community.document_loaders.BSHTMLLoader",
        "allowdTypes": ["html", "htm"],
    },
    {
        "loader": "CSVLoader",
        "name": "CSV (.csv)",
        "import": "langchain_community.document_loaders.CSVLoader",
        "defaultFor": ["csv"],
        "allowdTypes": ["csv"],
    },
    {
        "loader": "CoNLLULoader",
        "name": "CoNLL-U (.conllu)",
        "import": "langchain_community.document_loaders.CoNLLULoader",
        "defaultFor": ["conllu"],
        "allowdTypes": ["conllu"],
    },
    {
        "loader": "EverNoteLoader",
        "name": "EverNote (.enex)",
        "import": "langchain_community.document_loaders.EverNoteLoader",
        "defaultFor": ["enex"],
        "allowdTypes": ["enex"],
    },
    {
        "loader": "FacebookChatLoader",
        "name": "Facebook Chat (.json)",
        "import": "langchain_community.document_loaders.FacebookChatLoader",
        "allowdTypes": ["json"],
    },
    {
        "loader": "OutlookMessageLoader",
        "name": "Outlook Message (.msg)",
        "import": "langchain_community.document_loaders.OutlookMessageLoader",
        "defaultFor": ["msg"],
        "allowdTypes": ["msg"],
    },
    {
        "loader": "PyPDFLoader",
        "name": "PyPDF (.pdf)",
        "import": "langchain_community.document_loaders.PyPDFLoader",
        "defaultFor": ["pdf"],
        "allowdTypes": ["pdf"],
    },
    {
        "loader": "STRLoader",
        "name": "Subtitle (.str)",
        "import": "langchain_community.document_loaders.STRLoader",
        "defaultFor": ["str"],
        "allowdTypes": ["str"],
    },
    {
        "loader": "TextLoader",
        "name": "Text (.txt)",
        "import": "langchain_community.document_loaders.TextLoader",
        "defaultFor": ["txt"],
        "allowdTypes": ["txt"],
    },
    {
        "loader": "UnstructuredEmailLoader",
        "name": "Unstructured Email (.eml)",
        "import": "langchain_community.document_loaders.UnstructuredEmailLoader",
        "defaultFor": ["eml"],
        "allowdTypes": ["eml"],
    },
    {
        "loader": "UnstructuredHTMLLoader",
        "name": "Unstructured HTML (.html, .htm)",
        "import": "langchain_community.document_loaders.UnstructuredHTMLLoader",
        "defaultFor": ["html", "htm"],
        "allowdTypes": ["html", "htm"],
    },
    {
        "loader": "UnstructuredMarkdownLoader",
        "name": "Unstructured Markdown (.md)",
        "import": "langchain_community.document_loaders.UnstructuredMarkdownLoader",
        "defaultFor": ["md", "mdx"],
        "allowdTypes": ["md", "mdx"],
    },
    {
        "loader": "UnstructuredPowerPointLoader",
        "name": "Unstructured PowerPoint (.pptx)",
        "import": "langchain_community.document_loaders.UnstructuredPowerPointLoader",
        "defaultFor": ["pptx"],
        "allowdTypes": ["pptx"],
    },
    {
        "loader": "UnstructuredWordLoader",
        "name": "Unstructured Word (.docx)",
        "import": "langchain_community.document_loaders.UnstructuredWordLoader",
        "defaultFor": ["docx"],
        "allowdTypes": ["docx"],
    },
]


MESSAGE_SENDER_AI = "Machine"
MESSAGE_SENDER_USER = "User"
MESSAGE_SENDER_NAME_AI = "AI"
MESSAGE_SENDER_NAME_USER = "User"

MAX_TEXT_LENGTH = 99999


SIDEBAR_CATEGORIES = [
    {"display_name": "Saved", "name": "saved_components", "icon": "GradientSave"},
    {"display_name": "Inputs", "name": "inputs", "icon": "Download"},
    {"display_name": "Outputs", "name": "outputs", "icon": "Upload"},
    {"display_name": "Prompts", "name": "prompts", "icon": "TerminalSquare"},
    {"display_name": "Data", "name": "data", "icon": "Database"},
    {"display_name": "Models", "name": "models", "icon": "BrainCircuit"},
    {"display_name": "Helpers", "name": "helpers", "icon": "Wand2"},
    {"display_name": "Vector Stores", "name": "vectorstores", "icon": "Layers"},
    {"display_name": "Embeddings", "name": "embeddings", "icon": "Binary"},
    {"display_name": "Agents", "name": "agents", "icon": "Bot"},
    {"display_name": "Astra Assistants", "name": "astra_assistants", "icon": "Sparkles"},
    {"display_name": "Chains", "name": "chains", "icon": "Link"},
    {"display_name": "Loaders", "name": "documentloaders", "icon": "Paperclip"},
    {"display_name": "Utilities", "name": "langchain_utilities", "icon": "PocketKnife"},
    {"display_name": "Link Extractors", "name": "link_extractors", "icon": "Link2"},
    {"display_name": "Memories", "name": "memories", "icon": "Cpu"},
    {"display_name": "Output Parsers", "name": "output_parsers", "icon": "Compass"},
    {"display_name": "Prototypes", "name": "prototypes", "icon": "FlaskConical"},
    {"display_name": "Retrievers", "name": "retrievers", "icon": "FileSearch"},
    {"display_name": "Text Splitters", "name": "textsplitters", "icon": "Scissors"},
    {"display_name": "Toolkits", "name": "toolkits", "icon": "Package2"},
    {"display_name": "Tools", "name": "tools", "icon": "Hammer"},
]

SIDEBAR_BUNDLES = [
    {"display_name": "OpenAI", "name": "openai_bundle", "icon": "OpenAiIcon"},
    {"display_name": "Azure", "name": "azure_bundle", "icon": "AzureIcon"},
    {"display_name": "Ollama", "name": "ollama_bundle", "icon": "OllamaIcon"},
    {"display_name": "Meta", "name": "meta_bundle", "icon": "MetaIcon"},
    {"display_name": "Amazon", "name": "amazon_bundle", "icon": "AWSIcon"},
    {"display_name": "Anthropic", "name": "anthropic_bundle", "icon": "AnthropicIcon"},
    {"display_name": "Google", "name": "google_bundle", "icon": "GoogleIcon"},
    {"display_name": "MongoDB", "name": "mongodb_bundle", "icon": "MongoDBIcon"},
    {"display_name": "Notion", "name": "notion_bundle", "icon": "NotionIcon"},
    {"display_name": "Redis", "name": "redis_bundle", "icon": "RedisIcon"},
    {"display_name": "Supabase", "name": "supabase_bundle", "icon": "SupabaseIcon"},
    {"display_name": "HuggingFace", "name": "huggingface_bundle", "icon": "HuggingFaceIcon"},
    {"display_name": "Cohere", "name": "cohere_bundle", "icon": "CohereIcon"},
    {"display_name": "Bing", "name": "bing_bundle", "icon": "BingIcon"},
    {"display_name": "Firecrawl", "name": "firecrawl_bundle", "icon": "FirecrawlIcon"},
    {"display_name": "Wikipedia", "name": "wikipedia_bundle", "icon": "SvgWikipedia"},
    {"display_name": "Wolfram", "name": "wolfram_bundle", "icon": "SvgWolfram"},
    {"display_name": "Maritalk", "name": "maritalk_bundle", "icon": "MaritalkIcon"},
    {"display_name": "PostgreSQL", "name": "postgres_bundle", "icon": "PostgresIcon"},
    {"display_name": "Baidu", "name": "baidu_bundle", "icon": "QianFanChatIcon"},
    {"display_name": "Vectara", "name": "vectara_bundle", "icon": "VectaraIcon"},
    {"display_name": "Cassandra", "name": "cassandra_bundle", "icon": "CassandraIcon"},
    {"display_name": "Chroma", "name": "chroma_bundle", "icon": "ChromaIcon"},
    {"display_name": "Couchbase", "name": "couchbase_bundle", "icon": "CouchbaseIcon"},
    {"display_name": "Clickhouse", "name": "clickhouse_bundle", "icon": "ClickhouseIcon"},
    {"display_name": "Airbyte", "name": "airbyte_bundle", "icon": "AirbyteIcon"},
    {"display_name": "AssemblyAI", "name": "assemblyai_bundle", "icon": "AssemblyAIIcon"},
    {"display_name": "AstraDB", "name": "astradb_bundle", "icon": "AstraDBIcon"},
    {"display_name": "Evernote", "name": "evernote_bundle", "icon": "EvernoteIcon"},
    {"display_name": "GitBook", "name": "gitbook_bundle", "icon": "GitBookIcon"},
    {"display_name": "Groq", "name": "groq_bundle", "icon": "GroqIcon"},
    {"display_name": "HCD", "name": "hcd_bundle", "icon": "HCDIcon"},
    {"display_name": "Hacker News", "name": "hackernews_bundle", "icon": "HackerNewsIcon"},
    {"display_name": "Unstructured", "name": "unstructured_bundle", "icon": "UnstructuredIcon"},
    {"display_name": "iFixit", "name": "ifixit_bundle", "icon": "IFixIcon"},
    {"display_name": "CrewAI", "name": "crewai_bundle", "icon": "CrewAiIcon"},
    {"display_name": "Composio", "name": "composio_bundle", "icon": "ComposioIcon"},
    {"display_name": "Midjourney", "name": "midjourney_bundle", "icon": "MidjourneyIcon"},
    {"display_name": "NVIDIA", "name": "nvidia_bundle", "icon": "NvidiaIcon"},
    {"display_name": "Pinecone", "name": "pinecone_bundle", "icon": "PineconeIcon"},
    {"display_name": "Qdrant", "name": "qdrant_bundle", "icon": "QDrantIcon"},
    {"display_name": "Elasticsearch", "name": "elasticsearch_bundle", "icon": "ElasticsearchIcon"},
    {"display_name": "Weaviate", "name": "weaviate_bundle", "icon": "WeaviateIcon"},
    {"display_name": "Searx", "name": "searx_bundle", "icon": "SearxIcon"},
    {"display_name": "Slack", "name": "slack_bundle", "icon": "SvgSlackIcon"},
    {"display_name": "Spider", "name": "spider_bundle", "icon": "SpiderIcon"},
    {"display_name": "MistralAI", "name": "mistralai_bundle", "icon": "MistralIcon"},
    {"display_name": "Upstash", "name": "upstash_bundle", "icon": "UpstashSvgIcon"},
    {"display_name": "PGVector", "name": "pgvector_bundle", "icon": "CpuIcon"},
    {"display_name": "Confluence", "name": "confluence_bundle", "icon": "ConfluenceIcon"},
    {"display_name": "AIML", "name": "aiml_bundle", "icon": "AIMLIcon"},
    {"display_name": "Git", "name": "git_bundle", "icon": "GitLoaderIcon"},
    {"display_name": "Athena", "name": "athena_bundle", "icon": "AthenaIcon"},
    {"display_name": "DuckDuckGo", "name": "duckduckgo_bundle", "icon": "DuckDuckGoIcon"},
    {"display_name": "Perplexity", "name": "perplexity_bundle", "icon": "Perplexity"},
    {"display_name": "OpenSearch", "name": "opensearch_bundle", "icon": "OpenSearch"},
    {"display_name": "Streamlit", "name": "streamlit_bundle", "icon": "Streamlit"},
]
