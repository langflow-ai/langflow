import clsx, { ClassValue } from "clsx";
import _ from "lodash";
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
  TerminalSquare,
  Wand2,
  Wrench,
} from "lucide-react";
import { ComponentType, SVGProps } from "react";
import { Connection, Edge, Node, ReactFlowInstance } from "reactflow";
import { twMerge } from "tailwind-merge";
import { ADJECTIVES, DESCRIPTIONS, NOUNS } from "./flow_constants";
import { AirbyteIcon } from "./icons/Airbyte";
import { AnthropicIcon } from "./icons/Anthropic";
import { BingIcon } from "./icons/Bing";
import { ChromaIcon } from "./icons/ChromaIcon";
import { CohereIcon } from "./icons/Cohere";
import { EvernoteIcon } from "./icons/Evernote";
import { FBIcon } from "./icons/FacebookMessenger";
import { GitBookIcon } from "./icons/GitBook";
import { GoogleIcon } from "./icons/Google";
import { HuggingFaceIcon } from "./icons/HuggingFace";
import { IFixIcon } from "./icons/IFixIt";
import { MetaIcon } from "./icons/Meta";
import { MidjourneyIcon } from "./icons/Midjorney";
import { MongoDBIcon } from "./icons/MongoDB";
import { NotionIcon } from "./icons/Notion";
import { OpenAiIcon } from "./icons/OpenAi";
import { PineconeIcon } from "./icons/Pinecone";
import { QDrantIcon } from "./icons/QDrant";
import { SearxIcon } from "./icons/Searx";
import { SlackIcon } from "./icons/Slack";
import { VertexAIIcon } from "./icons/VertexAI";
import { HackerNewsIcon } from "./icons/hackerNews";
import { SupabaseIcon } from "./icons/supabase";
import { APITemplateType } from "./types/api";
import { IVarHighlightType } from "./types/components";
import { FlowType, NodeType } from "./types/flow";

export function classNames(...classes: Array<string>) {
  return classes.filter(Boolean).join(" ");
}

export const limitScrollFieldsModal = 10;

export enum TypeModal {
  TEXT = 1,
  PROMPT = 2,
}

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
  return str.split("_").join(" ");
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
  return nodes.filter((node) => node.id === targetId || node.id === sourceId);
}

export function isValidConnection(
  { source, target, sourceHandle, targetHandle }: Connection,
  reactFlowInstance: ReactFlowInstance
) {
  if (
    targetHandle
      .split("|")[0]
      .split(";")
      .some((n) => n === sourceHandle.split("|")[0]) ||
    sourceHandle
      .split("|")
      .slice(2)
      .some((t) =>
        targetHandle
          .split("|")[0]
          .split(";")
          .some((n) => n === t)
      ) ||
    targetHandle.split("|")[0] === "str"
  ) {
    let targetNode = reactFlowInstance?.getNode(target)?.data?.node;
    if (!targetNode) {
      if (
        !reactFlowInstance
          .getEdges()
          .find((e) => e.targetHandle === targetHandle)
      ) {
        return true;
      }
    } else if (
      (!targetNode.template[targetHandle.split("|")[1]].list &&
        !reactFlowInstance
          .getEdges()
          .find((e) => e.targetHandle === targetHandle)) ||
      targetNode.template[targetHandle.split("|")[1]].list
    ) {
      return true;
    }
  }
  return false;
}

export function removeApiKeys(flow: FlowType): FlowType {
  let cleanFLow = _.cloneDeep(flow);
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

export function groupByFamily(data, baseClasses, left, type) {
  let parentOutput: string;
  let arrOfParent: string[] = [];
  let arrOfType: { family: string; type: string; component: string }[] = [];
  let arrOfLength: { length: number; type: string }[] = [];
  let lastType = "";
  Object.keys(data).map((d) => {
    Object.keys(data[d]).map((n) => {
      try {
        if (
          data[d][n].base_classes.some((r) =>
            baseClasses.split("\n").includes(r)
          )
        ) {
          arrOfParent.push(d);
        }
        if (n === type) {
          parentOutput = d;
        }

        if (d !== lastType) {
          arrOfLength.push({
            length: Object.keys(data[d]).length,
            type: d,
          });

          lastType = d;
        }
      } catch (e) {
        console.log(e);
      }
    });
  });

  Object.keys(data).map((d) => {
    Object.keys(data[d]).map((n) => {
      try {
        baseClasses.split("\n").forEach((tol) => {
          data[d][n].base_classes.forEach((data) => {
            if (tol == data) {
              arrOfType.push({
                family: d,
                type: data,
                component: n,
              });
            }
          });
        });
      } catch (e) {
        console.log(e);
      }
    });
  });

  if (left === false) {
    let groupedBy = arrOfType.filter((object, index, self) => {
      const foundIndex = self.findIndex(
        (o) => o.family === object.family && o.type === object.type
      );
      return foundIndex === index;
    });

    return groupedBy.reduce((result, item) => {
      const existingGroup = result.find(
        (group) => group.family === item.family
      );

      if (existingGroup) {
        existingGroup.type += `, ${item.type}`;
      } else {
        result.push({
          family: item.family,
          type: item.type,
          component: item.component,
        });
      }

      if (left === false) {
        let resFil = result.filter((group) => group.family === parentOutput);
        result = resFil;
      }

      return result;
    }, []);
  } else {
    const groupedArray = [];
    const groupedData = {};

    arrOfType.forEach((item) => {
      const { family, type, component } = item;
      const key = `${family}-${type}`;

      if (!groupedData[key]) {
        groupedData[key] = { family, type, component: [component] };
      } else {
        groupedData[key].component.push(component);
      }
    });

    for (const key in groupedData) {
      groupedArray.push(groupedData[key]);
    }

    groupedArray.forEach((object, index, self) => {
      const findObj = arrOfLength.find((x) => x.type === object.family);
      if (object.component.length === findObj.length) {
        self[index]["type"] = "";
      } else {
        self[index]["type"] = object.component.join(", ");
      }
    });
    return groupedArray;
  }
}

export function buildInputs(tabsState, id) {
  return tabsState &&
    tabsState[id] &&
    tabsState[id].formKeysData &&
    tabsState[id].formKeysData.input_keys &&
    Object.keys(tabsState[id].formKeysData.input_keys).length > 0
    ? JSON.stringify(tabsState[id].formKeysData.input_keys)
    : '{"input": "message"}';
}

export function buildTweaks(flow) {
  return flow.data.nodes.reduce((acc, node) => {
    acc[node.data.id] = {};
    return acc;
  }, {});
}
export function validateNode(
  n: NodeType,
  reactFlowInstance: ReactFlowInstance
): Array<string> {
  if (!n.data?.node?.template || !Object.keys(n.data.node.template)) {
    return [
      "We've noticed a potential issue with a node in the flow. Please review it and, if necessary, submit a bug report with your exported flow file. Thank you for your help!",
    ];
  }

  const {
    type,
    node: { template },
  } = n.data;

  return Object.keys(template).reduce(
    (errors: Array<string>, t) =>
      errors.concat(
        template[t].required &&
          template[t].show &&
          (template[t].value === undefined ||
            template[t].value === null ||
            template[t].value === "") &&
          !reactFlowInstance
            .getEdges()
            .some(
              (e) =>
                e.targetHandle.split("|")[1] === t &&
                e.targetHandle.split("|")[2] === n.id
            )
          ? [
              `${type} is missing ${
                template.display_name || toNormalCase(template[t].name)
              }.`,
            ]
          : []
      ),
    [] as string[]
  );
}

export function validateNodes(reactFlowInstance: ReactFlowInstance) {
  if (reactFlowInstance.getNodes().length === 0) {
    return [
      "No nodes found in the flow. Please add at least one node to the flow.",
    ];
  }
  return reactFlowInstance
    .getNodes()
    .flatMap((n: NodeType) => validateNode(n, reactFlowInstance));
}

export function getRandomElement<T>(array: T[]): T {
  return array[Math.floor(Math.random() * array.length)];
}
export function getRandomDescription(): string {
  return getRandomElement(DESCRIPTIONS);
}

export function getRandomName(
  retry: number = 0,
  noSpace: boolean = false,
  maxRetries: number = 3
): string {
  const left: string[] = ADJECTIVES;
  const right: string[] = NOUNS;

  const lv = getRandomElement(left);
  const rv = getRandomElement(right);

  // Condition to avoid "boring wozniak"
  if (lv === "boring" && rv === "wozniak") {
    if (retry < maxRetries) {
      return getRandomName(retry + 1, noSpace, maxRetries);
    } else {
      console.warn("Max retries reached, returning as is");
    }
  }

  // Append a suffix if retrying and noSpace is true
  if (retry > 0 && noSpace) {
    const retrySuffix = Math.floor(Math.random() * 10);
    return `${lv}_${rv}${retrySuffix}`;
  }

  // Construct the final name
  let final_name = noSpace ? `${lv}_${rv}` : `${lv} ${rv}`;
  // Return title case final name
  return toTitleCase(final_name);
}

export function getRandomKeyByssmm(): string {
  const now = new Date();
  const seconds = String(now.getSeconds()).padStart(2, "0");
  const milliseconds = String(now.getMilliseconds()).padStart(3, "0");
  return seconds + milliseconds + Math.abs(Math.floor(Math.random() * 10001));
}

export const INVALID_CHARACTERS = [
  " ",
  ",",
  ".",
  ":",
  ";",
  "!",
  "?",
  "/",
  "\\",
  "(",
  ")",
  "[",
  "]",
  "\n",
];

export const regexHighlight = /\{([^}]+)\}/g;

export const varHighlightHTML = ({ name }: IVarHighlightType) => {
  const html = `<span class="font-semibold chat-message-highlight">{${name}}</span>`;
  return html;
};
