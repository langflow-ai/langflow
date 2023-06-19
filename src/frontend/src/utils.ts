import { NodeDataType } from "./types/flow/index";
import {
  RocketLaunchIcon,
  LinkIcon,
  CpuChipIcon,
  LightBulbIcon,
  CommandLineIcon,
  WrenchScrewdriverIcon,
  WrenchIcon,
  ComputerDesktopIcon,
  GiftIcon,
  PaperClipIcon,
  QuestionMarkCircleIcon,
  FingerPrintIcon,
  ScissorsIcon,
  CircleStackIcon,
  Squares2X2Icon,
  PencilSquareIcon,
  Square3Stack3DIcon,
} from "@heroicons/react/24/outline";
import {
  Connection,
  Edge,
  Node,
  OnSelectionChangeParams,
  ReactFlowInstance,
  ReactFlowJsonObject,
  XYPosition,
} from "reactflow";
import { FlowType, NodeType } from "./types/flow";
import { APITemplateType } from "./types/api";
import _ from "lodash";
import { ChromaIcon } from "./icons/ChromaIcon";
import { AnthropicIcon } from "./icons/Anthropic";
import { AirbyteIcon } from "./icons/Airbyte";
import { BingIcon } from "./icons/Bing";
import { CohereIcon } from "./icons/Cohere";
import { EvernoteIcon } from "./icons/Evernote";
import { FBIcon } from "./icons/FacebookMessenger";
import { GitBookIcon } from "./icons/GitBook";
import { GoogleIcon } from "./icons/Google";
import { HackerNewsIcon } from "./icons/hackerNews";
import { HugginFaceIcon } from "./icons/HuggingFace";
import { IFixIcon } from "./icons/IFixIt";
import { MetaIcon } from "./icons/Meta";
import { MidjorneyIcon } from "./icons/Midjorney";
import { NotionIcon } from "./icons/Notion";
import { OpenAiIcon } from "./icons/OpenAi";
import { QDrantIcon } from "./icons/QDrant";
import { SearxIcon } from "./icons/Searx";
import { SlackIcon } from "./icons/Slack";
import clsx, { ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function classNames(...classes: Array<string>) {
  return classes.filter(Boolean).join(" ");
}

export const limitScrollFieldsModal = 10;

export enum TypeModal {
  TEXT = 1,
  PROMPT = 2,
}

export const textColors = {
  white: "text-white",
  red: "text-red-700",
  orange: "text-orange-700",
  amber: "text-amber-700",
  yellow: "text-yellow-700",
  lime: "text-lime-700",
  green: "text-green-700",
  emerald: "text-emerald-700",
  teal: "text-teal-700",
  cyan: "text-cyan-700",
  sky: "text-sky-700",
  blue: "text-blue-700",
  indigo: "text-indigo-700",
  violet: "text-violet-700",
  purple: "text-purple-700",
  fuchsia: "text-fuchsia-700",
  pink: "text-pink-700",
  rose: "text-rose-700",
  black: "text-black-700",
  gray: "text-gray-700",
};

export const borderLColors = {
  white: "border-l-white",
  red: "border-l-red-500",
  orange: "border-l-orange-500",
  amber: "border-l-amber-500",
  yellow: "border-l-yellow-500",
  lime: "border-l-lime-500",
  green: "border-l-green-500",
  emerald: "border-l-emerald-500",
  teal: "border-l-teal-500",
  cyan: "border-l-cyan-500",
  sky: "border-l-sky-500",
  blue: "border-l-blue-500",
  indigo: "border-l-indigo-500",
  violet: "border-l-violet-500",
  purple: "border-l-purple-500",
  fuchsia: "border-l-fuchsia-500",
  pink: "border-l-pink-500",
  rose: "border-l-rose-500",
  black: "border-l-black-500",
  gray: "border-l-gray-500",
};

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
  connectors: "#E6A627",
  unknown: "#9CA3AF",
  custom: "#9CA3AF",
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
  utilities: "Utilities",
  connectors: "Connectors",
  unknown: "Unknown",
  custom: "Custom",
};

export const nodeIcons: {
  [char: string]: React.ForwardRefExoticComponent<
    React.SVGProps<SVGSVGElement>
  >;
} = {
  Chroma: ChromaIcon,
  AirbyteJSONLoader: AirbyteIcon,
  // SerpAPIWrapper: SerperIcon,
  // AZLyricsLoader: AzIcon,
  Anthropic: AnthropicIcon,
  ChatAnthropic: AnthropicIcon,
  BingSearchAPIWrapper: BingIcon,
  BingSearchRun: BingIcon,
  Cohere: CohereIcon,
  CohereEmbeddings: CohereIcon,
  EverNoteLoader: EvernoteIcon,
  FacebookChatLoader: FBIcon,
  GitbookLoader: GitBookIcon,
  GoogleSearchAPIWrapper: GoogleIcon,
  GoogleSearchResults: GoogleIcon,
  GoogleSearchRun: GoogleIcon,
  HNLoader: HackerNewsIcon,
  HuggingFaceHub: HugginFaceIcon,
  HuggingFaceEmbeddings: HugginFaceIcon,
  IFixitLoader: IFixIcon,
  Meta: MetaIcon,
  Midjorney: MidjorneyIcon,
  NotionDirectoryLoader: NotionIcon,
  ChatOpenAI: OpenAiIcon,
  OpenAI: OpenAiIcon,
  OpenAIEmbeddings: OpenAiIcon,
  // UnstructuredPowerPointLoader: PowerPointIcon, // word and powerpoint have differente styles
  Qdrant: QDrantIcon,
  // ReadTheDocsLoader: ReadTheDocsIcon, // does not work
  Searx: SearxIcon,
  SlackDirectoryLoader: SlackIcon,
  // Weaviate: WeaviateIcon, // does not work
  // WikipediaAPIWrapper: WikipediaIcon,
  // WolframAlphaQueryRun: WolframIcon,
  // WolframAlphaAPIWrapper: WolframIcon,
  // UnstructuredWordDocumentLoader: WordIcon, // word and powerpoint have differente styles
  agents: RocketLaunchIcon,
  chains: LinkIcon,
  memories: CpuChipIcon,
  llms: LightBulbIcon,
  prompts: CommandLineIcon,
  tools: WrenchIcon,
  advanced: ComputerDesktopIcon,
  chat: Bars3CenterLeftIcon,
  embeddings: FingerPrintIcon,
  documentloaders: PaperClipIcon,
  vectorstores: CircleStackIcon,
  toolkits: WrenchScrewdriverIcon,
  textsplitters: ScissorsIcon,
  wrappers: GiftIcon,
  utilities: Squares2X2Icon,
  connectors: Square3Stack3DIcon,
  unknown: QuestionMarkCircleIcon,
  custom: PencilSquareIcon,
};

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
];

export const bgColors = {
  white: "bg-white",
  red: "bg-red-100",
  orange: "bg-orange-100",
  amber: "bg-amber-100",
  yellow: "bg-yellow-100",
  lime: "bg-lime-100",
  green: "bg-green-100",
  emerald: "bg-emerald-100",
  teal: "bg-teal-100",
  cyan: "bg-cyan-100",
  sky: "bg-sky-100",
  blue: "bg-blue-100",
  indigo: "bg-indigo-100",
  violet: "bg-violet-100",
  purple: "bg-purple-100",
  fuchsia: "bg-fuchsia-100",
  pink: "bg-pink-100",
  rose: "bg-rose-100",
  black: "bg-black-100",
  gray: "bg-gray-100",
};

export const bgColorsHover = {
  white: "hover:bg-white",
  black: "hover:bg-black-50",
  gray: "hover:bg-gray-50",
  red: "hover:bg-red-50",
  orange: "hover:bg-orange-50",
  amber: "hover:bg-amber-50",
  yellow: "hover:bg-yellow-50",
  lime: "hover:bg-lime-50",
  green: "hover:bg-green-50",
  emerald: "hover:bg-emerald-50",
  teal: "hover:bg-teal-50",
  cyan: "hover:bg-cyan-50",
  sky: "hover:bg-sky-50",
  blue: "hover:bg-blue-50",
  indigo: "hover:bg-indigo-50",
  violet: "hover:bg-violet-50",
  purple: "hover:bg-purple-50",
  fuchsia: "hover:bg-fuchsia-50",
  pink: "hover:bg-pink-50",
  rose: "hover:bg-rose-50",
};

export const textColorsHex = {
  red: "rgb(185 28 28)",
  orange: "rgb(194 65 12)",
  amber: "rgb(180 83 9)",
  yellow: "rgb(161 98 7)",
  lime: "rgb(77 124 15)",
  green: "rgb(21 128 61)",
  emerald: "rgb(4 120 87)",
  teal: "rgb(15 118 110)",
  cyan: "rgb(14 116 144)",
  sky: "rgb(3 105 161)",
  blue: "rgb(29 78 216)",
  indigo: "rgb(67 56 202)",
  violet: "rgb(109 40 217)",
  purple: "rgb(126 34 206)",
  fuchsia: "rgb(162 28 175)",
  pink: "rgb(190 24 93)",
  rose: "rgb(190 18 60)",
};

export const bgColorsHex = {
  red: "rgb(254 226 226)",
  orange: "rgb(255 237 213)",
  amber: "rgb(254 243 199)",
  yellow: "rgb(254 249 195)",
  lime: "rgb(236 252 203)",
  green: "rgb(220 252 231)",
  emerald: "rgb(209 250 229)",
  teal: "rgb(204 251 241)",
  cyan: "rgb(207 250 254)",
  sky: "rgb(224 242 254)",
  blue: "rgb(219 234 254)",
  indigo: "rgb(224 231 255)",
  violet: "rgb(237 233 254)",
  purple: "rgb(243 232 255)",
  fuchsia: "rgb(250 232 255)",
  pink: "rgb(252 231 243)",
  rose: "rgb(255 228 230)",
};

export const taskTypeMap: { [key: string]: string } = {
  MULTICLASS_CLASSIFICATION: "Multiclass Classification",
};

const charWidths: { [char: string]: number } = {
  " ": 0.2,
  "!": 0.2,
  '"': 0.3,
  "#": 0.5,
  $: 0.5,
  "%": 0.5,
  "&": 0.5,
  "(": 0.2,
  ")": 0.2,
  "*": 0.5,
  "+": 0.5,
  ",": 0.2,
  "-": 0.2,
  ".": 0.1,
  "/": 0.5,
  ":": 0.2,
  ";": 0.2,
  "<": 0.5,
  "=": 0.5,
  ">": 0.5,
  "?": 0.2,
  "@": 0.5,
  "[": 0.2,
  "\\": 0.5,
  "]": 0.2,
  "^": 0.5,
  _: 0.2,
  "`": 0.5,
  "{": 0.2,
  "|": 0.2,
  "}": 0.2,
  "~": 0.5,
};

for (let i = 65; i <= 90; i++) {
  charWidths[String.fromCharCode(i)] = 0.6;
}
for (let i = 97; i <= 122; i++) {
  charWidths[String.fromCharCode(i)] = 0.5;
}

export function measureTextWidth(text: string, fontSize: number) {
  let wordWidth = 0;
  for (let j = 0; j < text.length; j++) {
    let char = text[j];
    let charWidth = charWidths[char] || 0.5;
    wordWidth += charWidth * fontSize;
  }
  return wordWidth;
}

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function measureTextHeight(
  text: string,
  width: number,
  fontSize: number
) {
  const charHeight = fontSize;
  const lineHeight = charHeight * 1.5;
  const words = text.split(" ");
  let lineWidth = 0;
  let totalHeight = 0;
  for (let i = 0; i < words.length; i++) {
    let word = words[i];
    let wordWidth = measureTextWidth(word, fontSize);
    if (lineWidth + wordWidth + charWidths[" "] * fontSize <= width) {
      lineWidth += wordWidth + charWidths[" "] * fontSize;
    } else {
      totalHeight += lineHeight;
      lineWidth = wordWidth;
    }
  }
  totalHeight += lineHeight;
  return totalHeight;
}

export function toCamelCase(str: string) {
  return str
    .split(" ")
    .map((word, index) =>
      index === 0
        ? word.toLowerCase()
        : word[0].toUpperCase() + word.slice(1).toLowerCase()
    )
    .join("");
}
export function toFirstUpperCase(str: string) {
  return str
    .split(" ")
    .map((word, index) => word[0].toUpperCase() + word.slice(1).toLowerCase())
    .join("");
}

export function snakeToSpaces(str: string) {
  let result = str.split("_").join(" ");

  return result;
}

export function toNormalCase(str: string) {
  let result = str
    .split("_")
    .map((word, index) => {
      if (index === 0) {
        return word[0].toUpperCase() + word.slice(1).toLowerCase();
      }
      return word.toLowerCase();
    })
    .join(" ");

  return result
    .split("-")
    .map((word, index) => {
      if (index === 0) {
        return word[0].toUpperCase() + word.slice(1).toLowerCase();
      }
      return word.toLowerCase();
    })
    .join(" ");
}

export function normalCaseToSnakeCase(str: string) {
  return str
    .split(" ")
    .map((word, index) => {
      if (index === 0) {
        return word[0].toUpperCase() + word.slice(1).toLowerCase();
      }
      return word.toLowerCase();
    })
    .join("_");
}

export function roundNumber(x: number, decimals: number) {
  return Math.round(x * Math.pow(10, decimals)) / Math.pow(10, decimals);
}

export function getConnectedNodes(edge: Edge, nodes: Array<Node>): Array<Node> {
  const sourceId = edge.source;
  const targetId = edge.target;
  const connectedNodes = nodes.filter(
    (node) => node.id === targetId || node.id === sourceId
  );
  return connectedNodes;
}

export function isValidConnection(
  { source, target, sourceHandle, targetHandle }: Connection,
  reactFlowInstance: ReactFlowInstance
) {
  console.log(source, target);
  // target is target id
  if (
    sourceHandle.split("|")[0] === targetHandle.split("|")[0] ||
    sourceHandle
      .split("|")
      .slice(2)
      .some((t) => t === targetHandle.split("|")[0]) ||
    targetHandle.split("|")[0] === "str"
  ) {
    let targetNode = reactFlowInstance.getNode(target).data.node;
    if (!targetNode) {
      if (
        !reactFlowInstance
          .getEdges()
          .find((e) => e.targetHandle === targetHandle)
      ) {
        return true;
      }
    } else if (
      //! === "Text" is not a good solution
      //TODO: fix this with a parameter
      targetHandle.split("|")[0] === "Text" &&
      target !== source &&
      !reactFlowInstance.getEdges().find((e) => e.targetHandle === targetHandle)
    ) {
      return true;
    } else if (
      targetNode.template[targetHandle.split("|")[1]] &&
      ((!targetNode.template[targetHandle.split("|")[1]].list &&
        !reactFlowInstance
          .getEdges()
          .find((e) => e.targetHandle === targetHandle)) ||
        targetNode.template[targetHandle.split("|")[1]].list)
    ) {
      return true;
    }
  }
  return false;
}

export function removeApiKeys(flow: FlowType): FlowType {
  let cleanFLow = _.cloneDeep(flow);
  console.log(cleanFLow);
  cleanFLow.data.nodes.forEach((node) => {
    for (const key in node.data.node.template) {
      if (node.data.node.template[key].password) {
        node.data.node.template[key].value = "";
      }
    }
  });
  return cleanFLow;
}

export function updateObject<T extends Record<string, any>>(
  reference: T,
  objectToUpdate: T
): T {
  let clonedObject = _.cloneDeep(objectToUpdate);
  // Loop through each key in the object to update
  for (const key in clonedObject) {
    // If the key is not in the reference object, delete it
    if (!(key in reference)) {
      delete clonedObject[key];
    }
  }
  // Loop through each key in the reference object
  for (const key in reference) {
    // If the key is not in the object to update, add it
    if (!(key in clonedObject)) {
      clonedObject[key] = reference[key];
    }
  }
  return clonedObject;
}

export function debounce(func, wait) {
  let timeout;
  return function (...args) {
    const context = this;
    clearTimeout(timeout);
    timeout = setTimeout(() => func.apply(context, args), wait);
  };
}

export function updateTemplate(
  reference: APITemplateType,
  objectToUpdate: APITemplateType
): APITemplateType {
  let clonedObject: APITemplateType = _.cloneDeep(reference);

  // Loop through each key in the reference object
  for (const key in clonedObject) {
    // If the key is not in the object to update, add it
    if (objectToUpdate[key] && objectToUpdate[key].value) {
      clonedObject[key].value = objectToUpdate[key].value;
    }
    if (
      objectToUpdate[key] &&
      objectToUpdate[key].advanced !== null &&
      objectToUpdate[key].advanced !== undefined
    ) {
      clonedObject[key].advanced = objectToUpdate[key].advanced;
    }
  }
  return clonedObject;
}

interface languageMap {
  [key: string]: string | undefined;
}

export const programmingLanguages: languageMap = {
  javascript: ".js",
  python: ".py",
  java: ".java",
  c: ".c",
  cpp: ".cpp",
  "c++": ".cpp",
  "c#": ".cs",
  ruby: ".rb",
  php: ".php",
  swift: ".swift",
  "objective-c": ".m",
  kotlin: ".kt",
  typescript: ".ts",
  go: ".go",
  perl: ".pl",
  rust: ".rs",
  scala: ".scala",
  haskell: ".hs",
  lua: ".lua",
  shell: ".sh",
  sql: ".sql",
  html: ".html",
  css: ".css",
  // add more file extensions here, make sure the key is same as language prop in CodeBlock.tsx component
};

export function getMiddlePoint(nodes: Node[]) {
  let middlePointX = 0;
  let middlePointY = 0;

  nodes.forEach((node) => {
    middlePointX += node.position.x;
    middlePointY += node.position.y;
  });

  const totalNodes = nodes.length;
  const averageX = middlePointX / totalNodes;
  const averageY = middlePointY / totalNodes;

  return { x: averageX, y: averageY };
}

export function generateFlow(
  selection: OnSelectionChangeParams,
  reactFlowInstance: ReactFlowInstance,
  name: string
): { newFlow: FlowType; removedEdges: Edge[] } {
  const newFlowData = reactFlowInstance.toObject();

  /*	remove edges that are not connected to selected nodes on both ends
		in future we can save this edges to when ungrouping reconect to the old nodes
	*/
  newFlowData.edges = selection.edges.filter(
    (edge) =>
      selection.nodes.some((node) => node.id === edge.target) &&
      selection.nodes.some((node) => node.id === edge.source)
  );
  newFlowData.nodes = selection.nodes;

  // console.log(newFlowData);
  const newFlow: FlowType = {
    data: newFlowData,
    name: name,
    description: "",
    id: uuidv4(),
  };
  // filter edges that are not connected to selected nodes on both ends
  // using O(n²) aproach because the number of edges is small
  // in the future we can use a better aproach using a set
  return {
    newFlow,
    removedEdges: selection.edges.filter(
      (edge) => !newFlowData.edges.includes(edge)
    ),
  };
}

export function filterFlow(
  selection: OnSelectionChangeParams,
  reactFlowInstance: ReactFlowInstance
) {
  reactFlowInstance.setNodes((nodes) =>
    nodes.filter((node) => !selection.nodes.includes(node))
  );
  reactFlowInstance.setEdges((edges) =>
    edges.filter((edge) => !selection.edges.includes(edge))
  );
}

export function generateNodeFromFlow(flow: FlowType): NodeType {
  const { nodes } = flow.data;
  const outputNode = _.cloneDeep(findLastNode(flow.data));
  // console.log(flow)
  const position = getMiddlePoint(nodes);
  let data = flow;
  const newGroupNode: NodeType = {
    data: {
      id: data.id,
      type: outputNode.data.type,
      value: null,
      node: {
        base_classes: outputNode.data.node.base_classes,
        description: "group Node",
        template: generateNodeTemplate(data),
        flow: data,
      },
    },
    id: data.id,
    position,
    type: "groupNode",
  };
  return newGroupNode;
}

export function concatFlows(
  flow: FlowType,
  ReactFlowInstance: ReactFlowInstance
) {
  const { nodes, edges } = flow.data;
  ReactFlowInstance.addNodes(nodes);
  ReactFlowInstance.addEdges(edges);
}
export function expandGroupNode(
  flow: FlowType,
  ReactFlowInstance: ReactFlowInstance,
  template: APITemplateType
) {
  const gNodes = _.cloneDeep(flow.data.nodes);
  const gEdges = flow.data.edges;
  //redirect edges to correct proxy node
  let updatedEdges: Edge[] = [];
  ReactFlowInstance.getEdges().forEach((edge) => {
    let newEdge = _.cloneDeep(edge);
    if (newEdge.target === flow.id) {
      if (newEdge.targetHandle.split("|").length > 3) {
        let type = newEdge.targetHandle.split("|")[0];
        let field = newEdge.targetHandle.split("|")[4];
        let proxy = newEdge.targetHandle.split("|")[3];
        let node = gNodes.find((n) => n.id === proxy);
        console.log(node);
        if (node) {
          newEdge.target = proxy;
          if (node.type === "groupNode") {
            newEdge.targetHandle =
              type +
              "|" +
              field +
              "|" +
              proxy +
              "|" +
              node.data.node.template[field].proxy.id +
              "|" +
              node.data.node.template[field].proxy.field;
          } else {
            newEdge.targetHandle = type + "|" + field + "|" + proxy;
          }
          updatedEdges.push(newEdge);
        }
      }
    }
    if (newEdge.source === flow.id) {
      const lastNode = _.cloneDeep(findLastNode(flow.data));
      newEdge.source = lastNode.id;
      let sourceHandle = newEdge.sourceHandle.split("|");
      sourceHandle[1] = lastNode.id;
      newEdge.sourceHandle = sourceHandle.join("|");
      updatedEdges.push(newEdge);
    }
  });

  Object.keys(template).forEach((key) => {
    let { field, id } = template[key].proxy;
    let nodeIndex = gNodes.findIndex((n) => n.id === id);
    if (nodeIndex !== -1) {
      let display_name: string;
      let show = gNodes[nodeIndex].data.node.template[field].show;
      let advanced = gNodes[nodeIndex].data.node.template[field].advanced;
      if (gNodes[nodeIndex].data.node.template[field].display_name) {
        display_name = gNodes[nodeIndex].data.node.template[field].display_name;
      } else {
        display_name = gNodes[nodeIndex].data.node.template[field].name;
      }
      gNodes[nodeIndex].data.node.template[field] = template[key];
      gNodes[nodeIndex].data.node.template[field].show = show;
      gNodes[nodeIndex].data.node.template[field].advanced = advanced;
      gNodes[nodeIndex].data.node.template[field].display_name = display_name;
    }
  });

  const nodes = [
    ...ReactFlowInstance.getNodes().filter((n) => n.id !== flow.id),
    ...gNodes,
  ];
  const edges = [
    ...ReactFlowInstance.getEdges().filter(
      (e) => e.target !== flow.id && e.source !== flow.id
    ),
    ...gEdges,
    ...updatedEdges,
  ];
  ReactFlowInstance.setNodes(nodes);
  ReactFlowInstance.setEdges(edges);
}

export function updateFlowPosition(NewPosition: XYPosition, flow: FlowType) {
  const middlePoint = getMiddlePoint(flow.data.nodes);
  let deltaPosition = {
    x: NewPosition.x - middlePoint.x,
    y: NewPosition.y - middlePoint.y,
  };
  flow.data.nodes.forEach((node) => {
    node.position.x += deltaPosition.x;
    node.position.y += deltaPosition.y;
  });
}

export function validateNode(n: NodeType, selection: OnSelectionChangeParams) {
  // case group node
  if (n.type === "groupNode") {
    if (selection.edges.some((edge) => edge.target === n.id)) {
      return [];
    } else {
      return ["Error on group node"];
    }
  }

  // case custom node
  if (
    !(n.data as NodeDataType)?.node?.template ||
    !Object.keys((n.data as NodeDataType).node.template)
  ) {
    return [
      "There is a inconsistente flow in the node, please check your flow",
    ];
  }

  const {
    type,
    node: { template },
  } = n.data as NodeDataType;

  return Object.keys(template).reduce(
    (errors: Array<string>, t) =>
      errors.concat(
        template[t].required &&
          template[t].show &&
          (!template[t].value || template[t].value === "") &&
          !selection.edges.some(
            (e) =>
              e.targetHandle.split("|")[1] === t &&
              e.targetHandle.split("|")[2] === n.id
          )
          ? [
              `${type} is missing ${
                template.display_name
                  ? template.display_name
                  : toNormalCase(template[t].name)
              }.`,
            ]
          : []
      ),
    [] as string[]
  );
}

export function validateSelection(
  selection: OnSelectionChangeParams
): Array<string> {
  let errorsArray: Array<string> = [];
  // check if there is more than one node
  if (selection.nodes.length < 2) {
    errorsArray.push("Please select more than one node");
  }

  //check if there are two or more nodes with free outputs
  if (
    selection.nodes.filter(
      (n) => !selection.edges.some((e) => e.source === n.id)
    ).length > 1
  ) {
    errorsArray.push("Please select only one node with free outputs");
  }

  // check if there is any node that does not have any connection
  if (
    selection.nodes.some(
      (node) =>
        !selection.edges.some((edge) => edge.target === node.id) &&
        !selection.edges.some((edge) => edge.source === node.id)
    )
  ) {
    errorsArray.push("Please select only nodes that are connected");
  }
  return errorsArray;
}
export function mergeNodeTemplates({
  nodes,
  edges,
}: {
  nodes: NodeType[];
  edges: Edge[];
}): APITemplateType | undefined {
  /* this function receives a flow and iterate trhow each node
		and merge the templates with only the visible fields
		if there are two keys with the same name in the flow, we will update the display name of each one
		to show from which node it came from
	*/
  let template: APITemplateType = {};
  nodes.forEach((node) => {
    let nodeTemplate = _.cloneDeep(node.data.node.template);
    Object.keys(nodeTemplate)
      .filter((field_name) => field_name.charAt(0) !== "_")
      .forEach((key) => {
        if (
          nodeTemplate[key].show &&
          !isHandleConnected(edges, key, nodeTemplate[key], node.id)
        ) {
          template[key + "_" + node.id] = nodeTemplate[key];
          template[key + "_" + node.id].proxy = { id: node.id, field: key };
          if (node.type === "groupNode") {
            template[key + "_" + node.id].display_name =
              node.data.node.flow.name + " - " + nodeTemplate[key].name;
          } else {
            template[key + "_" + node.id].display_name =
              node.data.type + " - " + nodeTemplate[key].name;
          }
        }
      });
  });
  return template;
}

function isHandleConnected(
  edges: Edge[],
  key: string,
  field: TemplateVariableType,
  nodeId: string
) {
  /*
		this function receives a flow and a handleId and check if there is a connection with this handle
	*/
  if (field.proxy) {
    if (
      edges.some(
        (e) =>
          e.targetHandle ===
          field.type +
            "|" +
            key +
            "|" +
            nodeId +
            "|" +
            field.proxy.id +
            "|" +
            field.proxy.field
      )
    ) {
      return true;
    }
  } else {
    if (
      edges.some(
        (e) => e.targetHandle === field.type + "|" + key + "|" + nodeId
      )
    ) {
      return true;
    }
  }
  return false;
}

function updateGroupNodeTemplate(template: APITemplateType) {
  /*this function receives a template, iterates for it's items
	updating the visibility of all basic types setting it to advanced true*/
  Object.keys(template).forEach((key) => {
    let type = template[key].type;
    if (
      (type === "str" ||
        type === "bool" ||
        type === "float" ||
        type === "code" ||
        type === "prompt" ||
        type === "file" ||
        type === "int") &&
      !template[key].required
    ) {
      template[key].advanced = true;
    }
  });
  return template;
}

export function generateNodeTemplate(Flow: FlowType) {
  /*
		this function receives a flow and generate a template for the group node
	*/
  let template = mergeNodeTemplates({
    nodes: Flow.data.nodes,
    edges: Flow.data.edges,
  });
  updateGroupNodeTemplate(template);
  return template;
}

export function findLastNode({
  nodes,
  edges,
}: {
  nodes: NodeType[];
  edges: Edge[];
}) {
  /*
		this function receives a flow and return the last node
	*/
  let lastNode = nodes.find((n) => !edges.some((e) => e.source === n.id));
  return lastNode;
}
// TODO: end this function
export function updateRemovedEdges(groupNode: NodeType, oldEdges: Edge[]) {
  /*
	this function receive a group node and the edges that were
	connected to the components that are now grouped and update the edges to the new node
	*/
  let FlowNodes = groupNode.data.node.flow.data.nodes;
  let newEdges: Edge[] = [];
  oldEdges.forEach((edge) => {
    let target = edge.target;
    const refNode = FlowNodes.find((node) => node.id === target);
    if (refNode) {
      //update edges to target node
      //consider two cases group node and normal node
    }
  });
}

export function ungroupNode(
  flow: FlowType,
  BaseFlow: ReactFlowJsonObject,
  template: APITemplateType
) {
  console.log(template);
  const gNodes: NodeType[] = flow.data.nodes;
  const gEdges = flow.data.edges;
  //redirect edges to correct proxy node
  let updatedEdges: Edge[] = [];
  BaseFlow.edges.forEach((edge) => {
    let newEdge = _.cloneDeep(edge);
    if (newEdge.target === flow.id) {
      if (newEdge.targetHandle.split("|").length > 3) {
        let type = newEdge.targetHandle.split("|")[0];
        let field = newEdge.targetHandle.split("|")[4];
        let proxy = newEdge.targetHandle.split("|")[3];
        let node = gNodes.find((n) => n.id === proxy);
        console.log(node);
        if (node) {
          newEdge.target = proxy;
          if (node.type === "groupNode") {
            newEdge.targetHandle =
              type +
              "|" +
              field +
              "|" +
              proxy +
              "|" +
              node.data.node.template[field].proxy.id +
              "|" +
              node.data.node.template[field].proxy.field;
          } else {
            newEdge.targetHandle = type + "|" + field + "|" + proxy;
          }
          updatedEdges.push(newEdge);
        }
      }
    }
    if (newEdge.source === flow.id) {
      const lastNode = _.cloneDeep(findLastNode(flow.data));
      newEdge.source = lastNode.id;
      let sourceHandle = newEdge.sourceHandle.split("|");
      sourceHandle[1] = lastNode.id;
      newEdge.sourceHandle = sourceHandle.join("|");
      updatedEdges.push(newEdge);
    }
  });
  Object.keys(template).forEach((key) => {
    let { field, id } = template[key].proxy;
    let nodeIndex = gNodes.findIndex((n) => n.id === id);
    if (nodeIndex !== -1) {
      let display_name: string;
      let show = gNodes[nodeIndex].data.node.template[field].show;
      let advanced = gNodes[nodeIndex].data.node.template[field].advanced;
      if (gNodes[nodeIndex].data.node.template[field].display_name) {
        display_name = gNodes[nodeIndex].data.node.template[field].display_name;
      } else {
        display_name = gNodes[nodeIndex].data.node.template[field].name;
      }
      gNodes[nodeIndex].data.node.template[field] = template[key];
      gNodes[nodeIndex].data.node.template[field].show = show;
      gNodes[nodeIndex].data.node.template[field].advanced = advanced;
      gNodes[nodeIndex].data.node.template[field].display_name = display_name;
    }
  });

  const nodes = [...BaseFlow.nodes.filter((n) => n.id !== flow.id), ...gNodes];
  const edges = [
    ...BaseFlow.edges.filter(
      (e) => e.target !== flow.id && e.source !== flow.id
    ),
    ...gEdges,
    ...updatedEdges,
  ];
  BaseFlow.nodes = nodes;
  BaseFlow.edges = edges;
}

export function processFLow(FlowObject: ReactFlowJsonObject) {
  let clonedFLow = _.cloneDeep(FlowObject);
  clonedFLow.nodes.forEach((node: NodeType) => {
    if (node.type === "groupNode") {
      processFLow(node.data.node.flow.data);
      ungroupNode(node.data.node.flow, clonedFLow, node.data.node.template);
    }
  });
  console.log(clonedFLow);
  return clonedFLow;
}

export function toTitleCase(str: string) {
  let result = str
    .split("_")
    .map((word, index) => {
      if (index === 0) {
        return checkUpperWords(
          word[0].toUpperCase() + word.slice(1).toLowerCase()
        );
      }
      return checkUpperWords(word.toLowerCase());
    })
    .join(" ");

  return result
    .split("-")
    .map((word, index) => {
      if (index === 0) {
        return checkUpperWords(
          word[0].toUpperCase() + word.slice(1).toLowerCase()
        );
      }
      return checkUpperWords(word.toLowerCase());
    })
    .join(" ");
}

export const upperCaseWords: string[] = ["llm", "uri"];
export function checkUpperWords(str: string) {
  const words = str.split(" ").map((word) => {
    return upperCaseWords.includes(word.toLowerCase())
      ? word.toUpperCase()
      : word[0].toUpperCase() + word.slice(1).toLowerCase();
  });

  return words.join(" ");
}

export function updateIds(newFlow, getNodeId) {
  let idsMap = {};

  newFlow.nodes.forEach((n: NodeType) => {
    // Generate a unique node ID
    let newId = getNodeId(n.data.type);
    idsMap[n.id] = newId;
    n.id = newId;
    n.data.id = newId;
    // Add the new node to the list of nodes in state
  });

  newFlow.edges.forEach((e) => {
    e.source = idsMap[e.source];
    e.target = idsMap[e.target];
    let sourceHandleSplitted = e.sourceHandle.split("|");
    e.sourceHandle =
      sourceHandleSplitted[0] +
      "|" +
      e.source +
      "|" +
      sourceHandleSplitted.slice(2).join("|");
    let targetHandleSplitted = e.targetHandle.split("|");
    e.targetHandle =
      targetHandleSplitted.slice(0, -1).join("|") + "|" + e.target;
    e.id =
      "reactflow__edge-" +
      e.source +
      e.sourceHandle +
      "-" +
      e.target +
      e.targetHandle;
  });
}

export function groupByFamily(data, baseClasses) {
  let arrOfParent: string[] = [];
  let arrOfType: { family: string; type: string }[] = [];

  Object.keys(data).map((d) => {
    Object.keys(data[d]).map((n) => {
      if (
        data[d][n].base_classes.some((r) => baseClasses.split("\n").includes(r))
      ) {
        arrOfParent.push(d);
      }
    });
  });

  let uniq = arrOfParent.filter(
    (item, index) => arrOfParent.indexOf(item) === index
  );

  Object.keys(data).map((d) => {
    Object.keys(data[d]).map((n) => {
      baseClasses.split("\n").forEach((tol) => {
        data[d][n].base_classes.forEach((data) => {
          if (tol == data) {
            arrOfType.push({
              family: d,
              type: data,
            });
          }
        });
      });
    });
  });

  let groupedBy = arrOfType.filter((object, index, self) => {
    const foundIndex = self.findIndex(
      (o) => o.family === object.family && o.type === object.type
    );
    return foundIndex === index;
  });

  let groupedObj = groupedBy.reduce((result, item) => {
    const existingGroup = result.find((group) => group.family === item.family);

    if (existingGroup) {
      existingGroup.type += `, ${item.type}`;
    } else {
      result.push({ family: item.family, type: item.type });
    }

    return result;
  }, []);

  return groupedObj;
}

export function connectedInputNodesOnHandle(
  nodeId: string,
  handleId: string,
  { nodes, edges }: { nodes: NodeType[]; edges: Edge[] }
) {
  const connectedNodes: Array<{ name: string; id: string; isGroup: boolean }> =
    [];
  // return the nodes connected to the input handle of the node
  const TargetEdges = edges.filter((e) => e.target === nodeId);
  TargetEdges.forEach((edge) => {
    if (edge.targetHandle === handleId) {
      const sourceNode = nodes.find((n) => n.id === edge.source);
      if (sourceNode) {
        if (sourceNode.type === "groupNode") {
          let lastNode = findLastNode(sourceNode.data.node.flow.data);
          while (lastNode && lastNode.type === "groupNode") {
            lastNode = findLastNode(lastNode.data.node.flow.data);
          }
          if (lastNode) {
            connectedNodes.push({
              name: sourceNode.data.node.flow.name,
              id: lastNode.id,
              isGroup: true,
            });
          }
        } else {
          connectedNodes.push({
            name: sourceNode.data.type,
            id: sourceNode.id,
            isGroup: false,
          });
        }
      }
    }
  });
  return connectedNodes;
}

function checkDuplicatedNames(
  connectedNodes: Array<{ name: string; id: string; isGroup: boolean }>
) {
  const names = connectedNodes.map((n) => n.name);
  const duplicatedNames = names.filter((n, i) => names.indexOf(n) !== i);
  return duplicatedNames;
}
