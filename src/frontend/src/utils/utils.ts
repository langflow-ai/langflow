import { ColDef, ColGroupDef } from "ag-grid-community";
import clsx, { ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import TableAutoCellRender from "../components/tableComponent/components/tableAutoCellRender";
import { MESSAGES_TABLE_ORDER, MODAL_CLASSES } from "../constants/constants";
import { APIDataType, InputFieldType, VertexDataTypeAPI } from "../types/api";
import {
  groupedObjType,
  nodeGroupedObjType,
  tweakType,
} from "../types/components";
import { NodeType } from "../types/flow";
import { FlowState } from "../types/tabs";
import { isErrorLog } from "../types/utils/typeCheckingUtils";

export function classNames(...classes: Array<string>): string {
  return classes.filter(Boolean).join(" ");
}

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function toNormalCase(str: string): string {
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

export function normalCaseToSnakeCase(str: string): string {
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

export function toTitleCase(
  str: string | undefined,
  isNodeField?: boolean,
): string {
  if (!str) return "";
  let result = str
    .split("_")
    .map((word, index) => {
      if (isNodeField) return word;
      if (index === 0) {
        return checkUpperWords(
          word[0].toUpperCase() + word.slice(1).toLowerCase(),
        );
      }
      return checkUpperWords(word.toLowerCase());
    })
    .join(" ");

  return result
    .split("-")
    .map((word, index) => {
      if (isNodeField) return word;
      if (index === 0) {
        return checkUpperWords(
          word[0].toUpperCase() + word.slice(1).toLowerCase(),
        );
      }
      return checkUpperWords(word.toLowerCase());
    })
    .join(" ");
}

export const upperCaseWords: string[] = ["llm", "uri"];
export function checkUpperWords(str: string): string {
  const words = str.split(" ").map((word) => {
    return upperCaseWords.includes(word.toLowerCase())
      ? word.toUpperCase()
      : word[0].toUpperCase() + word.slice(1).toLowerCase();
  });

  return words.join(" ");
}

export function buildInputs(): string {
  return '{"input_value": "message"}';
}

export function getRandomKeyByssmm(): string {
  const now = new Date();
  const seconds = String(now.getSeconds()).padStart(2, "0");
  const milliseconds = String(now.getMilliseconds()).padStart(3, "0");
  return seconds + milliseconds + Math.abs(Math.floor(Math.random() * 10001));
}

export function buildTweakObject(tweak: tweakType) {
  tweak.forEach((el) => {
    Object.keys(el).forEach((key) => {
      for (let kp in el[key]) {
        try {
          el[key][kp] = JSON.parse(el[key][kp]);
        } catch {}
      }
    });
  });
  const tweakString = JSON.stringify(tweak.at(-1), null, 2);
  return tweakString;
}

/**
 * Function to get Chat Input Field
 * @param {FlowsState} tabsState - The current tabs state.
 * @returns {string} - The chat input field
 */
export function getChatInputField(flowState?: FlowState) {
  let chat_input_field = "text";

  if (flowState && flowState.input_keys) {
    chat_input_field = Object.keys(flowState.input_keys!)[0];
  }
  return chat_input_field;
}

export function getOutputIds(flow) {
  const nodes = flow.data!.nodes;

  const arrayOfOutputs = nodes.reduce((acc: string[], node) => {
    if (node.data.type.toLowerCase().includes("output")) {
      acc.push(node.id);
    }
    return acc;
  }, []);

  const arrayOfOutputsJoin = arrayOfOutputs
    .map((output) => `"${output}"`)
    .join(", ");

  return arrayOfOutputsJoin;
}

export function truncateLongId(id: string): string {
  let [componentName, newId] = id.split("-");
  if (componentName.length > 15) {
    componentName = componentName.slice(0, 15);
    componentName += "...";
    return componentName + "-" + newId;
  }
  return id;
}

export function extractIdFromLongId(id: string): string {
  let [_, newId] = id.split("-");
  return newId;
}

export function truncateDisplayName(name: string): string {
  if (name.length > 15) {
    name = name.slice(0, 15);
    name += "...";
  }
  return name;
}

export function checkLocalStorageKey(key: string): boolean {
  return localStorage.getItem(key) !== null;
}

export function IncrementObjectKey(
  object: object,
  key: string,
): { newKey: string; increment: number } {
  let count = 1;
  const type = removeCountFromString(key);
  let newKey = type + " " + `(${count})`;
  while (object[newKey]) {
    count++;
    newKey = type + " " + `(${count})`;
  }
  return { newKey, increment: count };
}

export function removeCountFromString(input: string): string {
  // Define a regex pattern to match the count in parentheses
  const pattern = /\s*\(\w+\)\s*$/;

  // Use the `replace` method to remove the matched pattern
  const result = input.replace(pattern, "");

  return result.trim(); // Trim any leading/trailing spaces
}

export function extractTypeFromLongId(id: string): string {
  let [newId, _] = id.split("-");
  return newId;
}

export function createRandomKey(key: string, uid: string): string {
  return removeCountFromString(key) + ` (${uid})`;
}

export function groupByFamily(
  data: APIDataType,
  baseClasses: string,
  left: boolean,
  flow?: NodeType[],
): groupedObjType[] {
  const baseClassesSet = new Set(baseClasses.split("\n"));
  let arrOfPossibleInputs: Array<{
    category: string;
    nodes: nodeGroupedObjType[];
    full: boolean;
    display_name?: string;
  }> = [];
  let arrOfPossibleOutputs: Array<{
    category: string;
    nodes: nodeGroupedObjType[];
    full: boolean;
    display_name?: string;
  }> = [];
  let checkedNodes = new Map();
  const excludeTypes = new Set(["bool", "float", "code", "file", "int"]);

  const checkBaseClass = (template: InputFieldType) => {
    return (
      template?.type &&
      template?.show &&
      ((!excludeTypes.has(template.type) &&
        baseClassesSet.has(template.type)) ||
        (template?.input_types &&
          template?.input_types.some((inputType) =>
            baseClassesSet.has(inputType),
          )))
    );
  };

  if (flow) {
    // se existir o flow
    for (const node of flow) {
      // para cada node do flow
      if (node!.data!.node!.flow || !node!.data!.node!.template) break; // não faz nada se o node for um group
      const nodeData = node.data;

      const foundNode = checkedNodes.get(nodeData.type); // verifica se o tipo do node já foi checado
      checkedNodes.set(nodeData.type, {
        hasBaseClassInTemplate:
          foundNode?.hasBaseClassInTemplate ||
          Object.values(nodeData.node!.template).some(checkBaseClass),
        hasBaseClassInBaseClasses:
          foundNode?.hasBaseClassInBaseClasses ||
          nodeData.node!.base_classes?.some((baseClass) =>
            baseClassesSet.has(baseClass),
          ), //seta como anterior ou verifica se o node tem base class
        displayName: nodeData.node?.display_name,
      });
    }
  }

  for (const [d, nodes] of Object.entries(data)) {
    let tempInputs: nodeGroupedObjType[] = [],
      tempOutputs: nodeGroupedObjType[] = [];

    for (const [n, node] of Object.entries(nodes!)) {
      let foundNode = checkedNodes.get(n);

      if (!foundNode) {
        foundNode = {
          hasBaseClassInTemplate: Object.values(node!.template).some(
            checkBaseClass,
          ),
          hasBaseClassInBaseClasses: node!.base_classes?.some((baseClass) =>
            baseClassesSet.has(baseClass),
          ),
          displayName: node?.display_name,
        };
      }

      if (foundNode.hasBaseClassInTemplate)
        tempInputs.push({ node: n, displayName: foundNode.displayName });
      if (foundNode.hasBaseClassInBaseClasses)
        tempOutputs.push({ node: n, displayName: foundNode.displayName });
    }

    const totalNodes = Object.keys(nodes!).length;

    if (tempInputs.length)
      arrOfPossibleInputs.push({
        category: d,
        nodes: tempInputs,
        full: tempInputs.length === totalNodes,
      });
    if (tempOutputs.length)
      arrOfPossibleOutputs.push({
        category: d,
        nodes: tempOutputs,
        full: tempOutputs.length === totalNodes,
      });
  }

  return left
    ? arrOfPossibleOutputs.map((output) => ({
        family: output.category,
        type: output.full
          ? ""
          : output.nodes.map((item) => item.node).join(", "),
        display_name: "",
      }))
    : arrOfPossibleInputs.map((input) => ({
        family: input.category,
        type: input.full ? "" : input.nodes.map((item) => item.node).join(", "),
        display_name: input.nodes.map((item) => item.displayName).join(", "),
      }));
}

// this function is used to get the set of keys from an object
export function getSetFromObject(obj: object, key?: string): Set<string> {
  const set = new Set<string>();
  if (key) {
    for (const objKey in obj) {
      set.add(obj[objKey][key]);
    }
  } else {
    for (const key in obj) {
      set.add(key);
    }
  }
  return set;
}

export function freezeObject(obj: any) {
  if (!obj) return obj;
  return JSON.parse(JSON.stringify(obj));
}
export function isTimeStampString(str: string): boolean {
  const timestampRegexA = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3}Z)?$/;
  const timestampRegexB = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{6})?$/;

  return timestampRegexA.test(str) || timestampRegexB.test(str);
}

export function extractColumnsFromRows(
  rows: object[],
  mode: "intersection" | "union",
  excludeColumns?: Array<string>,
): (ColDef<any> | ColGroupDef<any>)[] {
  let columnsKeys: { [key: string]: ColDef<any> | ColGroupDef<any> } = {};
  if (rows.length === 0) {
    return [];
  }
  function intersection() {
    for (const key in rows[0]) {
      columnsKeys[key] = {
        headerName: key,
        field: key,
        cellRenderer: TableAutoCellRender,
        filter: true,
      };
    }
    for (const row of rows) {
      for (const key in columnsKeys) {
        if (!row[key]) {
          delete columnsKeys[key];
        }
      }
    }
  }
  function union() {
    for (const row of rows) {
      for (const key in row) {
        columnsKeys[key] = {
          headerName: key,
          field: key,
          filter: true,
          cellRenderer: TableAutoCellRender,
          suppressAutoSize: true,
          tooltipField: key,
        };
      }
    }
  }

  if (mode === "intersection") {
    intersection();
  } else {
    union();
  }

  if (excludeColumns) {
    for (const key of excludeColumns) {
      delete columnsKeys[key];
    }
  }

  return Object.values(columnsKeys);
}

export function isThereModal(): boolean {
  const modal = document.body.getElementsByClassName(MODAL_CLASSES);
  return modal.length > 0;
}

export function messagesSorter(a: any, b: any) {
  const indexA = MESSAGES_TABLE_ORDER.indexOf(a.field);
  const indexB = MESSAGES_TABLE_ORDER.indexOf(b.field);

  // If the field is not in the MESSAGES_TABLE_ORDER, we can place it at the end.
  const orderA = indexA === -1 ? MESSAGES_TABLE_ORDER.length : indexA;
  const orderB = indexB === -1 ? MESSAGES_TABLE_ORDER.length : indexB;

  return orderA - orderB;
}

export const logHasMessage = (
  data: VertexDataTypeAPI,
  outputName: string | undefined,
) => {
  if (!outputName) return;
  const outputs = data?.outputs[outputName];
  if (Array.isArray(outputs) && outputs.length > 1) {
    return outputs.some((outputLog) => outputLog.message);
  } else {
    return outputs?.message;
  }
};

export const logTypeIsUnknown = (
  data: VertexDataTypeAPI,
  outputName: string | undefined,
) => {
  if (!outputName) return;
  const outputs = data?.outputs[outputName];
  if (Array.isArray(outputs) && outputs.length > 1) {
    return outputs.some((outputLog) => outputLog.type === "unknown");
  } else {
    return outputs?.type === "unknown";
  }
};

export const logTypeIsError = (
  data: VertexDataTypeAPI,
  outputName: string | undefined,
) => {
  if (!outputName) return;
  const outputs = data?.outputs[outputName];
  if (Array.isArray(outputs) && outputs.length > 1) {
    return outputs.some((log) => isErrorLog(log));
  } else {
    return isErrorLog(outputs);
  }
};

export function isEndpointNameValid(name: string, maxLength: number): boolean {
  return (
    (/^[a-zA-Z0-9_-]+$/.test(name) && name.length <= maxLength) ||
    // empty is also valid
    name.length === 0
  );
}
