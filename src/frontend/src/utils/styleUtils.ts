import {
  Compass,
  Cpu,
  FileSearch,
  Fingerprint,
  Gift,
  Hammer,
  HelpCircle,
  Laptop2,
  Layers,
  Lightbulb,
  Link,
  MessageCircle,
  Paperclip,
  Rocket,
  Scissors,
  SlackIcon,
  TerminalSquare,
  Wand2,
  Wrench,
} from "lucide-react";
import { ComponentType, SVGProps } from "react";
import { Edge, Node } from "reactflow";
import { AirbyteIcon } from "../icons/Airbyte";
import { AnthropicIcon } from "../icons/Anthropic";
import { BingIcon } from "../icons/Bing";
import { ChromaIcon } from "../icons/ChromaIcon";
import { CohereIcon } from "../icons/Cohere";
import { EvernoteIcon } from "../icons/Evernote";
import { FBIcon } from "../icons/FacebookMessenger";
import { GitBookIcon } from "../icons/GitBook";
import { GoogleIcon } from "../icons/Google";
import { HuggingFaceIcon } from "../icons/HuggingFace";
import { IFixIcon } from "../icons/IFixIt";
import { MetaIcon } from "../icons/Meta";
import { MidjourneyIcon } from "../icons/Midjorney";
import { MongoDBIcon } from "../icons/MongoDB";
import { NotionIcon } from "../icons/Notion";
import { OpenAiIcon } from "../icons/OpenAi";
import { PineconeIcon } from "../icons/Pinecone";
import { QDrantIcon } from "../icons/QDrant";
import { SearxIcon } from "../icons/Searx";
import { VertexAIIcon } from "../icons/VertexAI";
import { HackerNewsIcon } from "../icons/hackerNews";
import { SupabaseIcon } from "../icons/supabase";

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

export const nodeColors: { [char: string]: string } = {
  prompts: "#4367BF",
  llms: "#6344BE",
  chains: "#FE7500",
  agents: "#903BBE",
  tools: "#FF3434",
  memories: "#F5B85A",
  advanced: "#000000",
  chat: "#198BF6",
  thought: "#272541",
  embeddings: "#42BAA7",
  documentloaders: "#7AAE42",
  vectorstores: "#AA8742",
  textsplitters: "#B47CB5",
  toolkits: "#DB2C2C",
  wrappers: "#E6277A",
  utilities: "#31A3CC",
  output_parsers: "#E6A627",
  str: "#049524",
  retrievers: "#e6b25a",
  unknown: "#9CA3AF",
};

export const nodeNames: { [char: string]: string } = {
  prompts: "Prompts",
  llms: "LLMs",
  chains: "Chains",
  agents: "Agents",
  tools: "Tools",
  memories: "Memories",
  advanced: "Advanced",
  chat: "Chat",
  embeddings: "Embeddings",
  documentloaders: "Loaders",
  vectorstores: "Vector Stores",
  toolkits: "Toolkits",
  wrappers: "Wrappers",
  textsplitters: "Text Splitters",
  retrievers: "Retrievers",
  utilities: "Utilities",
  output_parsers: "Output Parsers",
  unknown: "Unknown",
};

export const nodeIconsLucide: {
  [char: string]: React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >;
} = {
  Chroma: ChromaIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  AirbyteJSONLoader: AirbyteIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  Anthropic: AnthropicIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  ChatAnthropic: AnthropicIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  BingSearchAPIWrapper: BingIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  BingSearchRun: BingIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  Cohere: CohereIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  CohereEmbeddings: CohereIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  EverNoteLoader: EvernoteIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  FacebookChatLoader: FBIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  GitbookLoader: GitBookIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  GoogleSearchAPIWrapper: GoogleIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  GoogleSearchResults: GoogleIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  GoogleSearchRun: GoogleIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  HNLoader: HackerNewsIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  HuggingFaceHub: HuggingFaceIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  HuggingFaceEmbeddings: HuggingFaceIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  IFixitLoader: IFixIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  Meta: MetaIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  Midjorney: MidjourneyIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  MongoDBAtlasVectorSearch: MongoDBIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  NotionDirectoryLoader: NotionIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  ChatOpenAI: OpenAiIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  OpenAI: OpenAiIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  OpenAIEmbeddings: OpenAiIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  Pinecone: PineconeIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  Qdrant: QDrantIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  Searx: SearxIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  SlackDirectoryLoader: SlackIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  SupabaseVectorStore: SupabaseIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  VertexAI: VertexAIIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  ChatVertexAI: VertexAIIcon as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  agents: Rocket as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  chains: Link as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  memories: Cpu as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  llms: Lightbulb as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  prompts: TerminalSquare as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  tools: Wrench as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  advanced: Laptop2 as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  chat: MessageCircle as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  embeddings: Fingerprint as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  documentloaders: Paperclip as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  vectorstores: Layers as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  toolkits: Hammer as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  textsplitters: Scissors as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  wrappers: Gift as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  utilities: Wand2 as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  output_parsers: Compass as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  retrievers: FileSearch as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
  unknown: HelpCircle as React.ForwardRefExoticComponent<
    ComponentType<SVGProps<SVGSVGElement>>
  >,
};

export function getConnectedNodes(edge: Edge, nodes: Array<Node>): Array<Node> {
  const sourceId = edge.source;
  const targetId = edge.target;
  return nodes.filter((node) => node.id === targetId || node.id === sourceId);
}
