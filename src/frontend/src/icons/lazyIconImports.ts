// Export the lazy loading mapping for icons
export const lazyIconsMapping = {
  AIML: () => import("@/icons/AIML").then((mod) => ({ default: mod.AIMLIcon })),
  AgentQL: () =>
    import("@/icons/AgentQL").then((mod) => ({ default: mod.AgentQLIcon })),
  Airbyte: () =>
    import("@/icons/Airbyte").then((mod) => ({ default: mod.AirbyteIcon })),
  Anthropic: () =>
    import("@/icons/Anthropic").then((mod) => ({ default: mod.AnthropicIcon })),
  Apify: () =>
    import("@/icons/Apify").then((mod) => ({ default: mod.ApifyIcon })),
  ApifyWhite: () =>
    import("@/icons/Apify").then((mod) => ({ default: mod.ApifyWhiteIcon })),
  ArXiv: () =>
    import("@/icons/ArXiv").then((mod) => ({ default: mod.ArXivIcon })),
  Arize: () =>
    import("@/icons/Arize").then((mod) => ({ default: mod.ArizeIcon })),
  AssemblyAI: () =>
    import("@/icons/AssemblyAI").then((mod) => ({
      default: mod.AssemblyAIIcon,
    })),
  AstraDB: () =>
    import("@/icons/AstraDB").then((mod) => ({ default: mod.AstraDBIcon })),
  Athena: () =>
    import("@/icons/athena").then((mod) => ({ default: mod.AthenaIcon })),
  AWS: () => import("@/icons/AWS").then((mod) => ({ default: mod.AWSIcon })),
  AWSInverted: () =>
    import("@/icons/AWSInverted").then((mod) => ({
      default: mod.AWSInvertedIcon,
    })),
  Azure: () =>
    import("@/icons/Azure").then((mod) => ({ default: mod.AzureIcon })),
  Bing: () => import("@/icons/Bing").then((mod) => ({ default: mod.BingIcon })),
  BotMessageSquareIcon: () =>
    import("@/icons/BotMessageSquare").then((mod) => ({
      default: mod.BotMessageSquareIcon,
    })),
  BWPython: () =>
    import("@/icons/BW python").then((mod) => ({ default: mod.BWPythonIcon })),
  Cassandra: () =>
    import("@/icons/Cassandra").then((mod) => ({ default: mod.CassandraIcon })),
  Chroma: () =>
    import("@/icons/ChromaIcon").then((mod) => ({ default: mod.ChromaIcon })),
  Cleanlab: () =>
    import("@/icons/Cleanlab").then((mod) => ({ default: mod.CleanlabIcon })),
  Clickhouse: () =>
    import("@/icons/Clickhouse").then((mod) => ({
      default: mod.ClickhouseIcon,
    })),
  Cloudflare: () =>
    import("@/icons/Cloudflare").then((mod) => ({
      default: mod.CloudflareIcon,
    })),
  Cohere: () =>
    import("@/icons/Cohere").then((mod) => ({ default: mod.CohereIcon })),
  Composio: () =>
    import("@/icons/Composio").then((mod) => ({ default: mod.ComposioIcon })),
  Confluence: () =>
    import("@/icons/Confluence").then((mod) => ({
      default: mod.ConfluenceIcon,
    })),
  Couchbase: () =>
    import("@/icons/Couchbase").then((mod) => ({ default: mod.CouchbaseIcon })),
  Claude: () =>
    import("@/icons/Claude").then((mod) => ({ default: mod.ClaudeIcon })),
  CrewAI: () =>
    import("@/icons/CrewAI").then((mod) => ({ default: mod.CrewAiIcon })),
  Cursor: () =>
    import("@/icons/Cursor").then((mod) => ({ default: mod.CursorIcon })),
  DeepSeek: () =>
    import("@/icons/DeepSeek").then((mod) => ({ default: mod.DeepSeekIcon })),
  Docling: () =>
    import("@/icons/Docling").then((mod) => ({ default: mod.DoclingIcon })),
  Dropbox: () =>
    import("@/icons/Dropbox").then((mod) => ({ default: mod.DropboxIcon })),
  DuckDuckGo: () =>
    import("@/icons/DuckDuckGo").then((mod) => ({
      default: mod.DuckDuckGoIcon,
    })),
  ElasticsearchStore: () =>
    import("@/icons/ElasticsearchStore").then((mod) => ({
      default: mod.ElasticsearchIcon,
    })),
  Evernote: () =>
    import("@/icons/Evernote").then((mod) => ({ default: mod.EvernoteIcon })),
  Exa: () => import("@/icons/Exa").then((mod) => ({ default: mod.ExaIcon })),
  FacebookMessenger: () =>
    import("@/icons/FacebookMessenger").then((mod) => ({
      default: mod.FBIcon,
    })),
  Firecrawl: () =>
    import("@/icons/Firecrawl").then((mod) => ({ default: mod.FirecrawlIcon })),
  FreezeAll: () =>
    import("@/icons/freezeAll").then((mod) => ({ default: mod.freezeAllIcon })),
  GitBook: () =>
    import("@/icons/GitBook").then((mod) => ({ default: mod.GitBookIcon })),
  GitLoader: () =>
    import("@/icons/GitLoader").then((mod) => ({ default: mod.GitLoaderIcon })),
  Glean: () =>
    import("@/icons/Glean").then((mod) => ({ default: mod.GleanIcon })),
  GlobeOk: () =>
    import("@/icons/globe-ok").then((mod) => ({ default: mod.GlobeOkIcon })),
  Google: () =>
    import("@/icons/Google").then((mod) => ({ default: mod.GoogleIcon })),
  GoogleDrive: () =>
    import("@/icons/GoogleDrive").then((mod) => ({
      default: mod.GoogleDriveIcon,
    })),
  Googlemeet: () =>
    import("@/icons/googlemeet").then((mod) => ({
      default: mod.GooglemeetIcon,
    })),
  GoogleTasks: () =>
    import("@/icons/GoogleTasks").then((mod) => ({
      default: mod.GoogleTasksIcon,
    })),
  Googlesheets: () =>
    import("@/icons/googlesheets").then((mod) => ({
      default: mod.GooglesheetsIcon,
    })),
  GoogleGenerativeAI: () =>
    import("@/icons/GoogleGenerativeAI").then((mod) => ({
      default: mod.GoogleGenerativeAIIcon,
    })),
  Gmail: () =>
    import("@/icons/gmail").then((mod) => ({ default: mod.GmailIcon })),
  Outlook: () =>
    import("@/icons/outlook").then((mod) => ({ default: mod.OutlookIcon })),
  Googlecalendar: () =>
    import("@/icons/googlecalendar").then((mod) => ({
      default: mod.GooglecalendarIcon,
    })),
  GradientInfinity: () =>
    import("@/icons/GradientSparkles").then((mod) => ({
      default: mod.GradientInfinity,
    })),
  Googlemaps: () =>
    import("@/icons/googlemaps").then((mod) => ({
      default: mod.GooglemapsIcon,
    })),
  Todoist: () =>
    import("@/icons/todoist").then((mod) => ({
      default: mod.TodoistIcon,
    })),
  Zoom: () =>
    import("@/icons/zoom").then((mod) => ({
      default: mod.ZoomIcon,
    })),
  GradientUngroup: () =>
    import("@/icons/GradientSparkles").then((mod) => ({
      default: mod.GradientUngroup,
    })),
  GradientSave: () =>
    import("@/icons/GradientSparkles").then((mod) => ({
      default: mod.GradientSave,
    })),
  GridHorizontal: () =>
    import("@/icons/GridHorizontal").then((mod) => ({
      default: mod.GridHorizontalIcon,
    })),
  Groq: () => import("@/icons/Groq").then((mod) => ({ default: mod.GroqIcon })),
  HackerNews: () =>
    import("@/icons/hackerNews").then((mod) => ({
      default: mod.HackerNewsIcon,
    })),
  HCD: () => import("@/icons/HCD").then((mod) => ({ default: mod.HCDIcon })),
  HomeAssistant: () =>
    import("@/icons/HomeAssistant").then((mod) => ({
      default: mod.HomeAssistantIcon,
    })),
  HuggingFace: () =>
    import("@/icons/HuggingFace").then((mod) => ({
      default: mod.HuggingFaceIcon,
    })),
  Icosa: () =>
    import("@/icons/Icosa").then((mod) => ({ default: mod.IcosaIcon })),
  IFixIt: () =>
    import("@/icons/IFixIt").then((mod) => ({ default: mod.IFixIcon })),
  javascript: () =>
    import("@/icons/JSicon").then((mod) => ({ default: mod.JSIcon })),
  JigsawStack: () =>
    import("@/icons/JigsawStack").then((mod) => ({
      default: mod.JigsawStackIcon,
    })),
  Linear: () =>
    import("@/icons/linear").then((mod) => ({ default: mod.LinearIcon })),
  LangChain: () =>
    import("@/icons/LangChain").then((mod) => ({ default: mod.LangChainIcon })),
  Langwatch: () =>
    import("@/icons/Langwatch").then((mod) => ({ default: mod.LangwatchIcon })),
  LMStudio: () =>
    import("@/icons/LMStudio").then((mod) => ({ default: mod.LMStudioIcon })),
  Maritalk: () =>
    import("@/icons/Maritalk").then((mod) => ({ default: mod.MaritalkIcon })),
  Mcp: () => import("@/icons/MCP").then((mod) => ({ default: mod.McpIcon })),
  Mem0: () => import("@/icons/Mem0").then((mod) => ({ default: mod.Mem0 })),
  Meta: () => import("@/icons/Meta").then((mod) => ({ default: mod.MetaIcon })),
  Midjourney: () =>
    import("@/icons/Midjorney").then((mod) => ({
      default: mod.MidjourneyIcon,
    })),
  Milvus: () =>
    import("@/icons/Milvus").then((mod) => ({ default: mod.MilvusIcon })),
  Mistral: () =>
    import("@/icons/mistral").then((mod) => ({ default: mod.MistralIcon })),
  MongoDB: () =>
    import("@/icons/MongoDB").then((mod) => ({ default: mod.MongoDBIcon })),
  Needle: () =>
    import("@/icons/Needle").then((mod) => ({ default: mod.NeedleIcon })),
  NotDiamond: () =>
    import("@/icons/NotDiamond").then((mod) => ({
      default: mod.NotDiamondIcon,
    })),
  Notion: () =>
    import("@/icons/Notion").then((mod) => ({ default: mod.NotionIcon })),
  Novita: () =>
    import("@/icons/Novita").then((mod) => ({ default: mod.NovitaIcon })),
  NVIDIA: () =>
    import("@/icons/Nvidia").then((mod) => ({ default: mod.NvidiaIcon })),
  Olivya: () =>
    import("@/icons/Olivya").then((mod) => ({ default: mod.OlivyaIcon })),
  Ollama: () =>
    import("@/icons/Ollama").then((mod) => ({ default: mod.OllamaIcon })),
  OpenAI: () =>
    import("@/icons/OpenAi").then((mod) => ({ default: mod.OpenAiIcon })),
  OpenRouter: () =>
    import("@/icons/OpenRouter").then((mod) => ({
      default: mod.OpenRouterIcon,
    })),
  OpenSearch: () =>
    import("@/icons/OpenSearch").then((mod) => ({ default: mod.OpenSearch })),
  Perplexity: () =>
    import("@/icons/Perplexity").then((mod) => ({
      default: mod.PerplexityIcon,
    })),
  Pinecone: () =>
    import("@/icons/Pinecone").then((mod) => ({ default: mod.PineconeIcon })),
  Postgres: () =>
    import("@/icons/Postgres").then((mod) => ({ default: mod.PostgresIcon })),
  Python: () =>
    import("@/icons/Python").then((mod) => ({ default: mod.PythonIcon })),
  QDrant: () =>
    import("@/icons/QDrant").then((mod) => ({ default: mod.QDrantIcon })),
  QianFanChat: () =>
    import("@/icons/QianFanChat").then((mod) => ({
      default: mod.QianFanChatIcon,
    })),
  Redis: () =>
    import("@/icons/Redis").then((mod) => ({ default: mod.RedisIcon })),
  Reddit: () =>
    import("@/icons/reddit").then((mod) => ({ default: mod.RedditIcon })),
  SambaNova: () =>
    import("@/icons/SambaNova").then((mod) => ({ default: mod.SambaNovaIcon })),
  ScrapeGraph: () =>
    import("@/icons/ScrapeGraphAI").then((mod) => ({
      default: mod.ScrapeGraph,
    })),
  SearchAPI: () =>
    import("@/icons/SearchAPI").then((mod) => ({ default: mod.SearchAPIIcon })),
  SearchLexical: () =>
    import("@/icons/SearchLexical").then((mod) => ({
      default: mod.SearchLexicalIcon,
    })),
  SearchHybrid: () =>
    import("@/icons/SearchHybrid").then((mod) => ({
      default: mod.SearchHybridIcon,
    })),
  SearchVector: () =>
    import("@/icons/SearchVector").then((mod) => ({
      default: mod.SearchVectorIcon,
    })),
  Searx: () =>
    import("@/icons/Searx").then((mod) => ({ default: mod.SearxIcon })),
  SerpSearch: () =>
    import("@/icons/SerpSearch").then((mod) => ({
      default: mod.SerpSearchIcon,
    })),
  Serper: () =>
    import("@/icons/Serper").then((mod) => ({ default: mod.SerperIcon })),
  Share: () =>
    import("@/icons/Share").then((mod) => ({ default: mod.ShareIcon })),
  Share2: () =>
    import("@/icons/Share2").then((mod) => ({ default: mod.Share2Icon })),
  Slack: () =>
    import("@/icons/Slack/SlackIcon").then((mod) => ({ default: mod.default })),
  Spider: () =>
    import("@/icons/Spider").then((mod) => ({ default: mod.SpiderIcon })),
  Streamlit: () =>
    import("@/icons/Streamlit").then((mod) => ({ default: mod.Streamlit })),
  Supabase: () =>
    import("@/icons/supabase").then((mod) => ({ default: mod.SupabaseIcon })),
  Tavily: () =>
    import("@/icons/Tavily").then((mod) => ({ default: mod.TavilyIcon })),
  ThumbDownCustom: () =>
    import("@/icons/thumbs").then((mod) => ({
      default: mod.ThumbDownIconCustom,
    })),
  ThumbUpCustom: () =>
    import("@/icons/thumbs").then((mod) => ({
      default: mod.ThumbUpIconCustom,
    })),
  TwelveLabs: () =>
    import("@/icons/TwelveLabs").then((mod) => ({
      default: mod.TwelveLabsIcon,
    })),
  TwitterX: () =>
    import("@/icons/Twitter X").then((mod) => ({
      default: mod.TwitterXIcon,
    })),
  Unstructured: () =>
    import("@/icons/Unstructured").then((mod) => ({
      default: mod.UnstructuredIcon,
    })),
  Upstash: () =>
    import("@/icons/Upstash").then((mod) => ({ default: mod.UpstashSvgIcon })),
  Vectara: () =>
    import("@/icons/VectaraIcon").then((mod) => ({ default: mod.VectaraIcon })),
  VertexAI: () =>
    import("@/icons/VertexAI").then((mod) => ({ default: mod.VertexAIIcon })),
  WatsonxAI: () =>
    import("@/icons/IBMWatsonx").then((mod) => ({
      default: mod.WatsonxAiIcon,
    })),
  Weaviate: () =>
    import("@/icons/Weaviate").then((mod) => ({ default: mod.WeaviateIcon })),
  Wikipedia: () =>
    import("@/icons/Wikipedia/Wikipedia").then((mod) => ({
      default: mod.default,
    })),
  Windsurf: () =>
    import("@/icons/Windsurf").then((mod) => ({ default: mod.WindsurfIcon })),
  Wolfram: () =>
    import("@/icons/Wolfram/Wolfram").then((mod) => ({ default: mod.default })),
  xAI: () => import("@/icons/xAI").then((mod) => ({ default: mod.XAIIcon })),
  YouTube: () =>
    import("@/icons/Youtube").then((mod) => ({ default: mod.YouTubeSvgIcon })),
  ZepMemory: () =>
    import("@/icons/ZepMemory").then((mod) => ({ default: mod.ZepMemoryIcon })),
};
