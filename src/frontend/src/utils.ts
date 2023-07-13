import clsx, { ClassValue } from "clsx";
import { ReactFlowInstance } from "reactflow";
import { twMerge } from "tailwind-merge";
import { ADJECTIVES, DESCRIPTIONS, NOUNS } from "./flow_constants";
import { IVarHighlightType } from "./types/components";
import { NodeType } from "./types/flow";

export function classNames(...classes: Array<string>) {
  return classes.filter(Boolean).join(" ");
}

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
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
