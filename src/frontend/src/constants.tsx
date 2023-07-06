// src/constants.tsx

import { FlowType } from "./types/flow";
import { buildTweaks } from "./utils";

/**
 * The base text for subtitle of Export Dialog (Toolbar)
 * @constant
 */
export const EXPORT_DIALOG_SUBTITLE = "Export flow as JSON file.";

/**
 * The base text for subtitle of Flow Settings (Menubar)
 * @constant
 */
export const SETTINGS_DIALOG_SUBTITLE = "Edit details about your project.";

/**
 * The base text for subtitle of Code Dialog (Toolbar)
 * @constant
 */
export const CODE_DIALOG_SUBTITLE =
  "Export your flow to use it with this code.";

/**
 * The base text for subtitle of Edit Node Dialog
 * @constant
 */
export const EDIT_DIALOG_SUBTITLE =
  "Adjust the configurations of your component. Define parameter visibility for the canvas view. Remember to save once you’re finished.";

/**
 * The base text for subtitle of Code Dialog
 * @constant
 */
export const CODE_PROMPT_DIALOG_SUBTITLE =
  "Edit your Python code. This code snippet accepts module import and a single function definition. Make sure that your function returns a string.";

/**
 * The base text for subtitle of Prompt Dialog
 * @constant
 */
export const PROMPT_DIALOG_SUBTITLE =
  "Create your prompt. Prompts can help guide the behavior of a Language Model.";

/**
 * The base text for subtitle of Text Dialog
 * @constant
 */
export const TEXT_DIALOG_SUBTITLE = "Edit your text.";

/**
 * Function to get the python code for the API
 * @param {string} flowId - The id of the flow
 * @returns {string} - The python code
 */
export const getPythonApiCode = (flow: FlowType, tweak?): string => {
  const flowId = flow.id;

  // create a dictionary of node ids and the values is an empty dictionary
  // flow.data.nodes.forEach((node) => {
  //   node.data.id
  // }
  const tweaks = buildTweaks(flow);
  return `import requests

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

def run_flow(message: str, flow_id: str, tweaks: dict = None) -> dict:
    """
    Run a flow with a given message and optional tweaks.

    :param message: The message to send to the flow
    :param flow_id: The ID of the flow to run
    :param tweaks: Optional tweaks to customize the flow
    :return: The JSON response from the flow
    """
    api_url = f"{BASE_API_URL}/{flow_id}"

    payload = {"inputs": {"input": message}}

    if tweaks:
        payload["tweaks"] = tweaks

    response = requests.post(api_url, json=payload)
    return response.json()

# Setup any tweaks you want to apply to the flow

print(run_flow("Your message", flow_id=FLOW_ID, tweaks=TWEAKS))`;
};
/**
 * Function to get the curl code for the API
 * @param {string} flowId - The id of the flow
 * @returns {string} - The curl code
 */
export const getCurlCode = (flow: FlowType, tweak?): string => {
  const flowId = flow.id;
  const tweaks = buildTweaks(flow);
  return `curl -X POST \\
  ${window.location.protocol}//${
    window.location.host
  }/api/v1/process/${flowId} \\
  -H 'Content-Type: application/json' \\
  -d '{"inputs": {"input": message}, "tweaks": ${
    tweak && tweak.length > 0
      ? buildTweakObject(tweak)
      : JSON.stringify(tweaks, null, 2)
  }}'`;
};
/**
 * Function to get the python code for the API
 * @param {string} flowName - The name of the flow
 * @returns {string} - The python code
 */
export const getPythonCode = (flow: FlowType, tweak?): string => {
  const flowName = flow.name;
  const tweaks = buildTweaks(flow);
  return `from langflow import load_flow_from_json
TWEAKS = ${
    tweak && tweak.length > 0
      ? buildTweakObject(tweak)
      : JSON.stringify(tweaks, null, 2)
  }
flow = load_flow_from_json("${flowName}.json", tweaks=TWEAKS)
# Now you can use it like any chain
flow("Hey, have you heard of Langflow?")`;
};

function buildTweakObject(tweak) {
  tweak.forEach((el) => {
    Object.keys(el).forEach((key) => {
      for (let kp in el[key]) {
        try {
          el[key][kp] = JSON.parse(el[key][kp]);
        } catch {}
      }
    });
  });

  const tweakString = JSON.stringify(tweak, null, 2);
  return tweakString;
}

/**
 * The base text for subtitle of Import Dialog
 * @constant
 */
export const IMPORT_DIALOG_SUBTITLE =
  "Upload a JSON file or select from the available community examples.";

/**
 * The base text for subtitle of code dialog
 * @constant
 */
export const EXPORT_CODE_DIALOG =
  "Generate the code to integrate your flow into an external application.";

/**
 * The base text for subtitle of code dialog
 * @constant
 */
export const COLUMN_DIV_STYLE =
  " w-full h-full flex overflow-auto flex-col bg-muted px-16 ";

/**
 * The base text for subtitle of code dialog
 * @constant
 */
export const NAV_DISPLAY_STYLE =
  " w-full flex justify-between py-12 pb-2 px-6 ";
/**
 * Header text for user projects
 * @constant
 *
 */
export const USER_PROJECTS_HEADER = "My Collection";
