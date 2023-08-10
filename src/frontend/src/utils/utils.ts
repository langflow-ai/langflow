import clsx, { ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { ADJECTIVES, DESCRIPTIONS, NOUNS } from "../flow_constants";
import { IVarHighlightType } from "../types/components";
import { FlowType, NodeType } from "../types/flow";
import { TabsState } from "../types/tabs";
import { buildTweaks } from "./reactflowUtils";

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

export const isWrappedWithClass = (event: any, className: string | undefined) =>
  event.target.closest(`.${className}`);

export function groupByFamily(data, baseClasses, left, flow?: NodeType[]) {
  const baseClassesSet = new Set(baseClasses.split("\n"));
  let arrOfPossibleInputs = [];
  let arrOfPossibleOutputs = [];
  let checkedNodes = new Map();
  const excludeTypes = new Set([
    "str",
    "bool",
    "float",
    "code",
    "prompt",
    "file",
    "int",
  ]);

  const checkBaseClass = (template: any) =>
    template.type &&
    template.show &&
    ((!excludeTypes.has(template.type) && baseClassesSet.has(template.type)) ||
      (template.input_types &&
        template.input_types.some((inputType) =>
          baseClassesSet.has(inputType)
        )));

  if (flow) {
    for (const node of flow) {
      const nodeData = node.data;
      const foundNode = checkedNodes.get(nodeData.type);
      checkedNodes.set(nodeData.type, {
        hasBaseClassInTemplate:
          foundNode?.hasBaseClassInTemplate ||
          Object.values(nodeData.node.template).some(checkBaseClass),
        hasBaseClassInBaseClasses:
          foundNode?.hasBaseClassInBaseClasses ||
          nodeData.node.base_classes.some((baseClass) =>
            baseClassesSet.has(baseClass)
          ),
      });
    }
  }

  for (const [d, nodes] of Object.entries(data)) {
    let tempInputs = [],
      tempOutputs = [];

    for (const [n, node] of Object.entries(nodes)) {
      let foundNode = checkedNodes.get(n);
      if (!foundNode) {
        foundNode = {
          hasBaseClassInTemplate: Object.values(node.template).some(
            checkBaseClass
          ),
          hasBaseClassInBaseClasses: node.base_classes.some((baseClass) =>
            baseClassesSet.has(baseClass)
          ),
        };
        checkedNodes.set(n, foundNode);
      }

      if (foundNode.hasBaseClassInTemplate) tempInputs.push(n);
      if (foundNode.hasBaseClassInBaseClasses) tempOutputs.push(n);
    }

    const totalNodes = Object.keys(nodes).length;
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
        type: output.full ? "" : output.nodes.join(", "),
      }))
    : arrOfPossibleInputs.map((input) => ({
        family: input.category,
        type: input.full ? "" : input.nodes.join(", "),
      }));
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

export function varHighlightHTML({ name }: IVarHighlightType): string {
  const html = `<span class="font-semibold chat-message-highlight">{${name}}</span>`;
  return html;
}

export function buildTweakObject(tweak) {
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
 * @param {FlowType} flow - The current flow.
 * @param {TabsState} tabsState - The current tabs state.
 * @returns {string} - The chat input field
 */
export function getChatInputField(flow: FlowType, tabsState?: TabsState) {
  let chat_input_field = "text";

  if (
    tabsState[flow.id] &&
    tabsState[flow.id].formKeysData &&
    tabsState[flow.id].formKeysData.input_keys
  ) {
    chat_input_field = Object.keys(
      tabsState[flow.id].formKeysData.input_keys
    )[0];
  }
  return chat_input_field;
}

/**
 * Function to get the python code for the API
 * @param {string} flowId - The id of the flow
 * @returns {string} - The python code
 */
export function getPythonApiCode(
  flow: FlowType,
  tweak?: any[],
  tabsState?: TabsState
): string {
  const flowId = flow.id;

  // create a dictionary of node ids and the values is an empty dictionary
  // flow.data.nodes.forEach((node) => {
  //   node.data.id
  // }
  const tweaks = buildTweaks(flow);
  const inputs = buildInputs(tabsState, flow.id);
  return `import requests
from typing import Optional

BASE_API_URL = "${window.location.protocol}//${
    window.location.host
  }/api/v1/process"
FLOW_ID = "${flowId}"
# You can tweak the flow by adding a tweaks dictionary
# e.g {"OpenAI-XXXXX": {"model_name": "gpt-4"}}
TWEAKS = ${
    tweak && tweak.length > 0
      ? buildTweakObject(tweak)
      : JSON.stringify(tweaks, null, 2)
  }

def run_flow(inputs: dict, flow_id: str, tweaks: Optional[dict] = None) -> dict:
    """
    Run a flow with a given message and optional tweaks.

    :param message: The message to send to the flow
    :param flow_id: The ID of the flow to run
    :param tweaks: Optional tweaks to customize the flow
    :return: The JSON response from the flow
    """
    api_url = f"{BASE_API_URL}/{flow_id}"

    payload = {"inputs": inputs}

    if tweaks:
        payload["tweaks"] = tweaks

    response = requests.post(api_url, json=payload)
    return response.json()

# Setup any tweaks you want to apply to the flow
inputs = ${inputs}
print(run_flow(inputs, flow_id=FLOW_ID, tweaks=TWEAKS))`;
}

/**
 * Function to get the curl code for the API
 * @param {string} flowId - The id of the flow
 * @returns {string} - The curl code
 */
export function getCurlCode(
  flow: FlowType,
  tweak?: any[],
  tabsState?: TabsState
): string {
  const flowId = flow.id;
  const tweaks = buildTweaks(flow);
  const inputs = buildInputs(tabsState, flow.id);

  return `curl -X POST \\
  ${window.location.protocol}//${
    window.location.host
  }/api/v1/process/${flowId} \\
  -H 'Content-Type: application/json' \\
  -d '{"inputs": ${inputs}, "tweaks": ${
    tweak && tweak.length > 0
      ? buildTweakObject(tweak)
      : JSON.stringify(tweaks, null, 2)
  }}'`;
}

/**
 * Function to get the python code for the API
 * @param {string} flow - The current flow
 * @returns {string} - The python code
 */
export function getPythonCode(
  flow: FlowType,
  tweak?: any[],
  tabsState?: TabsState
): string {
  const flowName = flow.name;
  const tweaks = buildTweaks(flow);
  const inputs = buildInputs(tabsState, flow.id);
  return `from langflow import load_flow_from_json
TWEAKS = ${
    tweak && tweak.length > 0
      ? buildTweakObject(tweak)
      : JSON.stringify(tweaks, null, 2)
  }
flow = load_flow_from_json("${flowName}.json", tweaks=TWEAKS)
# Now you can use it like any chain
inputs = ${inputs}
flow(inputs)`;
}

/**
 * Function to get the widget code for the API
 * @param {string} flow - The current flow.
 * @returns {string} - The widget code
 */
export function getWidgetCode(flow: FlowType, tabsState?: TabsState): string {
  const flowId = flow.id;
  const flowName = flow.name;
  const inputs = buildInputs(tabsState, flow.id);
  let chat_input_field = getChatInputField(flow, tabsState);

  return `<script src="https://cdn.jsdelivr.net/gh/logspace-ai/langflow-embedded-chat@main/dist/build/static/js/bundle.min.js"></script>

<!-- chat_inputs: Stringified JSON with all the input keys and its values. The value of the key that is defined
as chat_input_field will be overwritten by the chat message.
chat_input_field: Input key that you want the chat to send the user message with. -->
<langflow-chat
  window_title="${flowName}"
  flow_id="${flowId}"
  ${
    tabsState[flow.id] && tabsState[flow.id].formKeysData
      ? `chat_inputs='${inputs}'
  chat_input_field="${chat_input_field}"
  `
      : ""
  }host_url="http://localhost:7860"
></langflow-chat>`;
}
