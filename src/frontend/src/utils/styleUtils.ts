import { TwitterLogoIcon } from "@radix-ui/react-icons";
import dynamicIconImports from "lucide-react/dynamicIconImports";
import { lazy } from "react";
import { FaApple, FaDiscord, FaGithub } from "react-icons/fa";
import { BotMessageSquareIcon } from "@/icons/BotMessageSquare";
import { fontAwesomeIcons, isFontAwesomeIcon } from "@/icons/fontAwesomeIcons";
import { GradientSave } from "@/icons/GradientSparkles";

const iconCache = new Map<string, any>();

export const BG_NOISE =
  "url(data:image/png;base64,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)";

export const gradients = [
  "bg-gradient-to-br from-gray-800 via-rose-700 to-violet-900",
  "bg-gradient-to-br from-green-200 via-green-300 to-blue-500",
  "bg-gradient-to-br from-yellow-200 via-yellow-400 to-yellow-700",
  "bg-gradient-to-br from-green-200 via-green-400 to-purple-700",
  "bg-gradient-to-br from-blue-100 via-blue-300 to-blue-500",
  "bg-gradient-to-br from-purple-400 to-yellow-400",
  "bg-gradient-to-br from-red-800 via-yellow-600 to-yellow-500",
  "bg-gradient-to-br from-blue-300 via-green-200 to-yellow-300",
  "bg-gradient-to-br from-blue-700 via-blue-800 to-gray-900",
  "bg-gradient-to-br from-green-300 to-purple-400",
  "bg-gradient-to-br from-yellow-200 via-pink-200 to-pink-400",
  "bg-gradient-to-br from-green-500 to-green-700",
  "bg-gradient-to-br from-rose-400 via-fuchsia-500 to-indigo-500",
  "bg-gradient-to-br from-sky-400 to-blue-500",
  "bg-gradient-to-br from-green-200 via-green-400 to-green-500",
  "bg-gradient-to-br from-red-400 via-gray-300 to-blue-500",
  "bg-gradient-to-br from-gray-900 to-gray-600 bg-gradient-to-r",
  "bg-gradient-to-br from-rose-500 via-red-400 to-red-500",
  "bg-gradient-to-br from-fuchsia-600 to-pink-600",
  "bg-gradient-to-br from-emerald-500 to-lime-600",
  "bg-gradient-to-br from-rose-500 to-indigo-700",
  "bg-gradient-to-br bg-gradient-to-tr from-violet-500 to-orange-300",
  "bg-gradient-to-br from-gray-900 via-purple-900 to-violet-600",
  "bg-gradient-to-br from-yellow-200 via-red-500 to-fuchsia-500",
  "bg-gradient-to-br from-sky-400 to-indigo-900",
  "bg-gradient-to-br from-amber-200 via-violet-600 to-sky-900",
  "bg-gradient-to-br from-amber-700 via-orange-300 to-rose-800",
  "bg-gradient-to-br from-gray-300 via-fuchsia-600 to-orange-600",
  "bg-gradient-to-br from-fuchsia-500 via-red-600 to-orange-400",
  "bg-gradient-to-br from-sky-400 via-rose-400 to-lime-400",
  "bg-gradient-to-br from-lime-600 via-yellow-300 to-red-600",
];

/*
Specifications
#FF3276 -> #F480FF
#1A0250 -> #2F10FE
#98F4FE -> #9BFEAA
#F480FF -> #7528FC
#F480FF -> #9BFEAA
#2F10FE -> #9BFEAA
#BB277F -> #050154
#7528FC -> #9BFEAA
#2F10FE -> #98F4FE
*/
export const flowGradients = [
  "linear-gradient(90deg, #FF3276 0%, #F480FF 100%)",
  "linear-gradient(90deg, #1A0250 0%, #2F10FE 100%)",
  "linear-gradient(90deg, #98F4FE 0%, #9BFEAA 100%)",
  "linear-gradient(90deg, #F480FF 0%, #7528FC 100%)",
  "linear-gradient(90deg, #F480FF 0%, #9BFEAA 100%)",
  "linear-gradient(90deg, #2F10FE 0%, #9BFEAA 100%)",
  "linear-gradient(90deg, #BB277F 0%, #050154 100%)",
  "linear-gradient(90deg, #7528FC 0%, #9BFEAA 100%)",
  "linear-gradient(90deg, #2F10FE 0%, #98F4FE 100%)",
];

export const toolModeGradient =
  "linear-gradient(-60deg,var(--tool-mode-gradient-1) 0%,var(--tool-mode-gradient-2) 100%)";

export const swatchColors = [
  "bg-neon-fuschia text-white",
  "bg-digital-orchid text-plasma-purple",
  "bg-plasma-purple text-digital-orchid",
  "bg-electric-blue text-holo-frost",
  "bg-holo-frost text-electric-blue",
  "bg-terminal-green text-cosmic-void",
];

export const nodeColors: { [char: string]: string } = {
  inputs: "#10B981",
  outputs: "#AA2411",
  data: "#198BF6",
  prompts: "#4367BF",
  models: "#ab11ab",
  model_specs: "#6344BE",
  chains: "#FE7500",
  list: "#9AAE42",
  agents: "#903BBE",
  Olivya: "#00413B",
  tools: "#00fbfc",
  memories: "#F5B85A",
  saved_components: "#a5B85A",
  advanced: "#000000",
  chat: "#198BF6",
  thought: "#272541",
  embeddings: "#42BAA7",
  documentloaders: "#7AAE42",
  vectorstores: "#AA8742",
  vectorsearch: "#AA8742",
  textsplitters: "#B47CB5",
  toolkits: "#DB2C2C",
  wrappers: "#E6277A",
  notion: "#000000",
  Notion: "#000000",
  AssemblyAI: "#213ED7",
  assemblyai: "#213ED7",
  helpers: "#31A3CC",
  prototypes: "#E6277A",
  astra_assistants: "#272541",
  langchain_utilities: "#31A3CC",
  output_parsers: "#E6A627",
  // custom_components: "#ab11ab",
  retrievers: "#e6b25a",
  str: "#4F46E5",
  Text: "#4F46E5",
  unknown: "#9CA3AF",
  Document: "#65a30d",
  Data: "#dc2626",
  Message: "#4f46e5",
  number: "#7E22CF",
  Prompt: "#7c3aed",
  Embeddings: "#10b981",
  BaseLanguageModel: "#c026d3",
  LanguageModel: "#c026d3",
  Agent: "#903BBE",
  AgentExecutor: "#903BBE",
  Tool: "#00fbfc",
};

export const nodeColorsName: { [char: string]: string } = {
  // custom_components: "#ab11ab",
  inputs: "emerald",
  outputs: "red",
  data: "sky",
  prompts: "blue",
  models: "fuchsia",
  model_specs: "violet",
  chains: "orange",
  list: "lime",
  agents: "purple",
  tools: "cyan",
  memories: "amber",
  saved_components: "lime",
  advanced: "slate",
  chat: "sky",
  thought: "zinc",
  embeddings: "teal",
  documentloaders: "lime",
  vectorstores: "yellow",
  vectorsearch: "yellow",
  textsplitters: "fuchsia",
  toolkits: "red",
  wrappers: "rose",
  notion: "slate",
  Notion: "slate",
  AssemblyAI: "blue",
  assemblyai: "blue",
  helpers: "cyan",
  prototypes: "rose",
  astra_assistants: "indigo",
  langchain_utilities: "sky",
  output_parsers: "yellow",
  retrievers: "yellow",
  str: "indigo",
  number: "purple",
  Text: "indigo",
  unknown: "gray",
  Document: "lime",
  Data: "red",
  Message: "indigo",
  Prompt: "violet",
  Embeddings: "emerald",
  BaseLanguageModel: "fuchsia",
  LanguageModel: "fuchsia",
  Agent: "purple",
  AgentExecutor: "purple",
  Tool: "cyan",
  BaseChatMemory: "cyan",
  BaseChatMessageHistory: "orange",
  Memory: "orange",
  DataFrame: "pink",
};

export const FILE_ICONS = {
  json: {
    icon: "FileJson",
    color: "text-datatype-indigo dark:text-datatype-indigo-foreground",
  },
  csv: {
    icon: "FileChartColumn",
    color: "text-datatype-emerald dark:text-datatype-emerald-foreground",
  },
  txt: {
    icon: "FileType",
    color: "text-datatype-purple dark:text-datatype-purple-foreground",
  },
  pdf: {
    icon: "File",
    color: "text-datatype-red dark:text-datatype-red-foreground",
  },
};

export const SIDEBAR_CATEGORIES = [
  { display_name: "Saved", name: "saved_components", icon: "GradientSave" },
  { display_name: "Input / Output", name: "input_output", icon: "Cable" },
  { display_name: "Agents", name: "agents", icon: "Bot" },
  { display_name: "Models", name: "models", icon: "BrainCog" },
  { display_name: "Data", name: "data", icon: "Database" },
  { display_name: "Vector Stores", name: "vectorstores", icon: "Layers" },
  { display_name: "Processing", name: "processing", icon: "ListFilter" },
  { display_name: "Logic", name: "logic", icon: "ArrowRightLeft" },
  { display_name: "Helpers", name: "helpers", icon: "Wand2" },
  { display_name: "Inputs", name: "inputs", icon: "Download" },
  { display_name: "Outputs", name: "outputs", icon: "Upload" },
  { display_name: "Prompts", name: "prompts", icon: "braces" },
  { display_name: "Chains", name: "chains", icon: "Link" },
  { display_name: "Loaders", name: "documentloaders", icon: "Paperclip" },
  { display_name: "Link Extractors", name: "link_extractors", icon: "Link2" },
  { display_name: "Output Parsers", name: "output_parsers", icon: "Compass" },
  { display_name: "Prototypes", name: "prototypes", icon: "FlaskConical" },
  { display_name: "Retrievers", name: "retrievers", icon: "FileSearch" },
  { display_name: "Text Splitters", name: "textsplitters", icon: "Scissors" },
  { display_name: "Toolkits", name: "toolkits", icon: "Package2" },
  { display_name: "Tools", name: "tools", icon: "Hammer" },
];

export const SIDEBAR_BUNDLES = [
  { display_name: "AI/ML API", name: "aiml", icon: "AIML" },
  { display_name: "AgentQL", name: "agentql", icon: "AgentQL" },
  { display_name: "Amazon", name: "amazon", icon: "Amazon" },
  { display_name: "Anthropic", name: "anthropic", icon: "Anthropic" },
  { display_name: "Apify", name: "apify", icon: "Apify" },

  { display_name: "arXiv", name: "arxiv", icon: "arXiv" },
  { display_name: "AssemblyAI", name: "assemblyai", icon: "AssemblyAI" },
  { display_name: "Azure", name: "azure", icon: "Azure" },
  { display_name: "Baidu", name: "baidu", icon: "BaiduQianfan" },
  { display_name: "Bing", name: "bing", icon: "Bing" },
  { display_name: "Cleanlab", name: "cleanlab", icon: "Cleanlab" },
  { display_name: "Cloudflare", name: "cloudflare", icon: "Cloudflare" },
  { display_name: "Cohere", name: "cohere", icon: "Cohere" },
  { display_name: "Composio", name: "composio", icon: "Composio" },
  { display_name: "Confluence", name: "confluence", icon: "Confluence" },
  { display_name: "CrewAI", name: "crewai", icon: "CrewAI" },
  { display_name: "DataStax", name: "datastax", icon: "AstraDB" },
  { display_name: "DeepSeek", name: "deepseek", icon: "DeepSeek" },
  { display_name: "Docling", name: "docling", icon: "Docling" },
  { display_name: "DuckDuckGo", name: "duckduckgo", icon: "DuckDuckGo" },
  { display_name: "Embeddings", name: "embeddings", icon: "Binary" },
  { display_name: "Exa", name: "exa", icon: "Exa" },
  { display_name: "Firecrawl", name: "firecrawl", icon: "FirecrawlCrawlApi" },
  { display_name: "Git", name: "git", icon: "GitLoader" },
  { display_name: "GitHub", name: "github", icon: "Github" },
  { display_name: "Glean", name: "glean", icon: "Glean" },
  { display_name: "Gmail", name: "gmail", icon: "Gmail" },
  { display_name: "Google", name: "google", icon: "Google" },
  {
    display_name: "Googlecalendar",
    name: "googlecalendar",
    icon: "Googlecalendar",
  },
  { display_name: "Groq", name: "groq", icon: "Groq" },
  {
    display_name: "Home Assistant",
    name: "homeassistant",
    icon: "HomeAssistant",
  },
  { display_name: "Hugging Face", name: "huggingface", icon: "HuggingFace" },
  { display_name: "IBM", name: "ibm", icon: "WatsonxAI" },
  { display_name: "Icosa Computing", name: "icosacomputing", icon: "Icosa" },
  { display_name: "JigsawStack", name: "jigsawstack", icon: "JigsawStack" },
  { display_name: "LangChain", name: "langchain_utilities", icon: "LangChain" },
  { display_name: "LangWatch", name: "langwatch", icon: "Langwatch" },
  { display_name: "LMStudio", name: "lmstudio", icon: "LMStudio" },
  { display_name: "MariTalk", name: "maritalk", icon: "Maritalk" },
  { display_name: "Mem0", name: "mem0", icon: "Mem0" },
  { display_name: "Memories", name: "memories", icon: "Cpu" },
  { display_name: "MistralAI", name: "mistral", icon: "MistralAI" },
  { display_name: "Needle", name: "needle", icon: "Needle" },
  { display_name: "Not Diamond", name: "notdiamond", icon: "NotDiamond" },
  { display_name: "Notion", name: "Notion", icon: "Notion" },
  { display_name: "Novita", name: "novita", icon: "Novita" },
  { display_name: "NVIDIA", name: "nvidia", icon: "NVIDIA" },
  { display_name: "Olivya", name: "olivya", icon: "Olivya" },
  { display_name: "Ollama", name: "ollama", icon: "Ollama" },
  { display_name: "OpenAI", name: "openai", icon: "OpenAI" },
  { display_name: "OpenRouter", name: "openrouter", icon: "OpenRouter" },
  { display_name: "Outlook", name: "outlook", icon: "Outlook" },
  { display_name: "Perplexity", name: "perplexity", icon: "Perplexity" },
  { display_name: "Redis", name: "redis", icon: "Redis" },
  { display_name: "SambaNova", name: "sambanova", icon: "SambaNova" },
  { display_name: "ScrapeGraph AI", name: "scrapegraph", icon: "ScrapeGraph" },
  { display_name: "SearchApi", name: "searchapi", icon: "SearchAPI" },
  { display_name: "SerpApi", name: "serpapi", icon: "SerpSearch" },
  { display_name: "Serper", name: "serper", icon: "Serper" },
  { display_name: "Tavily", name: "tavily", icon: "TavilyIcon" },
  { display_name: "TwelveLabs", name: "twelvelabs", icon: "TwelveLabs" },
  { display_name: "Unstructured", name: "unstructured", icon: "Unstructured" },
  { display_name: "Vectara", name: "vectara", icon: "Vectara" },
  { display_name: "Vertex AI", name: "vertexai", icon: "VertexAI" },
  { display_name: "Wikipedia", name: "wikipedia", icon: "Wikipedia" },
  {
    display_name: "WolframAlpha",
    name: "wolframalpha",
    icon: "WolframAlphaAPI",
  },
  { display_name: "xAI", name: "xai", icon: "xAI" },
  { display_name: "Yahoo! Finance", name: "yahoosearch", icon: "trending-up" },
  { display_name: "YouTube", name: "youtube", icon: "YouTube" },
  { display_name: "Zep", name: "zep", icon: "ZepMemory" },
];

export const categoryIcons: Record<string, string> = {
  saved_components: "GradientSave",
  input_output: "Cable",
  inputs: "Download",
  outputs: "Upload",
  prompts: "Braces",
  data: "Database",
  models: "BrainCircuit",
  helpers: "Wand2",
  vectorstores: "Layers",
  embeddings: "Binary",
  agents: "Bot",
  astra_assistants: "Sparkles",
  chains: "Link",
  documentloaders: "Paperclip",
  langchain_utilities: "PocketKnife",
  link_extractors: "Link2",
  memories: "Cpu",
  output_parsers: "Compass",
  prototypes: "FlaskConical",
  retrievers: "FileSearch",
  textsplitters: "Scissors",
  toolkits: "Package2",
  tools: "Hammer",
  custom: "Edit",
  custom_components: "GradientInfinity",
};

export const nodeIconToDisplayIconMap: Record<string, string> = {
  //Category Icons
  input_output: "Cable",
  inputs: "Download",
  outputs: "Upload",
  prompts: "Braces",
  data: "Database",
  models: "BrainCog",
  helpers: "Wand2",
  vectorstores: "Layers",
  embeddings: "Binary",
  agents: "Bot",
  astra_assistants: "Sparkles",
  chains: "Link",
  documentloaders: "Paperclip",
  langchain_utilities: "PocketKnife",
  link_extractors: "Link2",
  memories: "Cpu",
  output_parsers: "Compass",
  prototypes: "FlaskConical",
  retrievers: "FileSearch",
  textsplitters: "Scissors",
  toolkits: "Package2",
  tools: "Hammer",
  custom_components: "GradientInfinity",
  ChatInput: "MessagesSquare",
  ChatOutput: "MessagesSquare",
  //Integration Icons
  Outlook: "Outlook",
  AIML: "AIML",
  AgentQL: "AgentQL",
  LanguageModels: "BrainCircuit",
  EmbeddingModels: "Binary",
  AirbyteJSONLoader: "Airbyte",
  AmazonBedrockEmbeddings: "AWS",
  Amazon: "AWS",
  arXiv: "ArXiv",
  assemblyai: "AssemblyAI",
  athenaIcon: "Athena",
  AzureChatOpenAi: "OpenAI",
  AzureOpenAiEmbeddings: "Azure",
  AzureOpenAiModel: "Azure",
  BaiduQianfan: "QianFanChat",
  BingSearchAPIWrapper: "Bing",
  BingSearchRun: "Bing",
  ChatAnthropic: "Anthropic",
  ChatOllama: "Ollama",
  ChatOllamaModel: "Ollama",
  ChatOpenAI: "OpenAI",
  ChatVertexAI: "VertexAI",
  ChevronsUpDownIcon: "ChevronsUpDown",
  ClearMessageHistory: "FileClock",
  CohereEmbeddings: "Cohere",
  Discord: "FaDiscord",
  ElasticsearchStore: "ElasticsearchStore",
  EverNoteLoader: "Evernote",
  ExaSearch: "Exa",
  FacebookChatLoader: "FacebookMessenger",
  FAISS: "Meta",
  FaissSearch: "Meta",
  FirecrawlCrawlApi: "Firecrawl",
  FirecrawlExtractApi: "Firecrawl",
  FirecrawlMapApi: "Firecrawl",
  FirecrawlScrapeApi: "Firecrawl",
  GitbookLoader: "GitBook",
  GoogleGenerativeAI: "GoogleGenerativeAI",
  GoogleSearchAPI: "Google",
  GoogleSearchAPIWrapper: "Google",
  GoogleSearchResults: "Google",
  GoogleSearchRun: "Google",
  GoogleSerperAPI: "Google",
  group_components: "GradientUngroup",
  HNLoader: "HackerNews",
  HuggingFaceEmbeddings: "HuggingFace",
  HuggingFaceHub: "HuggingFace",
  IFixitLoader: "IFixIt",
  ListFlows: "Group",
  MistralAI: "Mistral",
  MongoDBAtlasVectorSearch: "MongoDB",
  MongoDBChatMessageHistory: "MongoDB",
  notion: "Notion",
  NotionDirectoryLoader: "Notion",
  NotDiamond: "NotDiamond",
  Notify: "Bell",
  novita: "Novita",
  OllamaEmbeddings: "Ollama",
  OpenAIEmbeddings: "OpenAI",
  PostgresChatMessageHistory: "Postgres",
  Qdrant: "QDrant",
  RedisSearch: "Redis",
  Share3: "Share",
  Share4: "Share2",
  SlackDirectoryLoader: "Slack",
  SpiderTool: "Spider",
  SupabaseVectorStore: "Supabase",
  TavilyIcon: "Tavily",
  VertexAIEmbeddings: "VertexAI",
  WikipediaAPIWrapper: "WikipediaAPI",
  WikipediaQueryRun: "WikipediaAPI",
  WolframAlphaAPI: "Wolfram",
  WolframAlphaAPIWrapper: "Wolfram",
  WolframAlphaQueryRun: "Wolfram",

  //Node Icons
  model_specs: "FileSliders",
  advanced: "Laptop2",
  chat: "MessageCircle",
  saved_components: "GradientSave",
  vectorsearch: "TextSearch",
  wrappers: "Gift",
  unknown: "HelpCircle",
  custom: "Edit",
  ThumbDownIconCustom: "ThumbDownCustom",
  ThumbUpIconCustom: "ThumbUpCustom",
  ScrapeGraphAI: "ScrapeGraph",
  ScrapeGraphSmartScraperApi: "ScrapeGraph",
  ScrapeGraphMarkdownifyApi: "ScrapeGraph",
  note: "StickyNote",
};

export const getLucideIconName = (name: string): string => {
  const map = {
    AlertCircle: "circle-alert",
    AlertTriangle: "triangle-alert",
    TerminalSquare: "square-terminal",
    Wand2: "wand-sparkles",
  };
  const kebabCaseName = name
    .replace(/Icon/g, "")
    .replace(/([a-z])([A-Z])/g, "$1-$2")
    .replace(/(\d)/g, "-$1")
    .replace(/\s+/g, "-")
    .toLowerCase();
  return map[name] || kebabCaseName;
};

// Initialize icon mappings based on if we want to support lazy loading for cloud
const iconMappingsPromise = import("../icons/lazyIconImports").then(
  (module) => module.lazyIconsMapping,
);

export const eagerLoadedIconsMap = {
  // Custom icons
  GradientSave: GradientSave,
  BotMessageSquareIcon: BotMessageSquareIcon,

  // React icon
  FaApple: FaApple,
  FaDiscord: FaDiscord,
  FaGithub: FaGithub,
  TwitterLogoIcon: TwitterLogoIcon,
};

export const getCachedIcon = (name: string) => {
  return iconCache.get(name);
};

export const getNodeIcon = async (name: string) => {
  const cacheAndReturn = (icon: any) => {
    iconCache.set(name, icon);
    return icon;
  };

  if (iconCache.has(name)) {
    return iconCache.get(name);
  }
  const iconName = nodeIconToDisplayIconMap[name];

  if (eagerLoadedIconsMap[iconName || name]) {
    return cacheAndReturn(eagerLoadedIconsMap[iconName || name]);
  }

  if (isFontAwesomeIcon(iconName || name)) {
    return cacheAndReturn(fontAwesomeIcons[iconName || name]);
  }

  const iconMappings = await iconMappingsPromise;

  if (iconMappings[iconName || name]) {
    return cacheAndReturn(lazy(iconMappings[iconName || name]));
  }

  const lucideIconName = getLucideIconName(iconName || name);
  if (dynamicIconImports[lucideIconName]) {
    try {
      return cacheAndReturn(lazy(dynamicIconImports[lucideIconName]));
    } catch (_e) {
      // Fall through to next option
    }
  }

  // If all else fails, return a simple empty component
  return cacheAndReturn(
    lazy(() =>
      Promise.resolve({
        default: () => null,
      }),
    ),
  );
};

export const iconExists = async (name: string): Promise<boolean> => {
  const iconName = nodeIconToDisplayIconMap[name] || name;
  const iconMappings = await iconMappingsPromise;

  return !!(
    eagerLoadedIconsMap[iconName] ||
    isFontAwesomeIcon(iconName) ||
    iconMappings[iconName] ||
    dynamicIconImports[getLucideIconName(iconName)]
  );
};
