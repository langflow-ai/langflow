// src/constants.tsx

/**
 * The base text for subtitle of Export Dialog (Toolbar)
 * @constant
 */
export const EXPORT_DIALOG_SUBTITLE = "Export your models.";

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
  "Make configurations changes to your nodes. Click save when you're done.";

/**
 * The base text for subtitle of Code Dialog
 * @constant
 */
export const CODE_PROMPT_DIALOG_SUBTITLE = "Edit you python code.";

/**
 * The base text for subtitle of Prompt Dialog
 * @constant
 */
export const PROMPT_DIALOG_SUBTITLE = "Edit you prompt.";

/**
 * The base text for subtitle of Text Dialog
 * @constant
 */
export const TEXT_DIALOG_SUBTITLE = "Edit you text.";

/**
 * Function to get the python code for the API
 * @param {string} flowId - The id of the flow
 * @returns {string} - The python code
 */
export const getPythonApiCode = (flowId: string): string => {
  return `import requests

  FLOW_ID = "${flowId}"
  API_URL = f"${window.location.protocol}//${window.location.host}/predict/{FLOW_ID}"

  def predict(message):
      payload = {'message': message}
      response = requests.post(API_URL, json=payload)
      return response.json()

  print(predict("Your message"))`;
};

/**
 * Function to get the curl code for the API
 * @param {string} flowId - The id of the flow
 * @returns {string} - The curl code
 */
export const getCurlCode = (flowId: string): string => {
  return `curl -X POST \\
  -H "Content-Type: application/json" \\
  -d '{"message": "Your message"}' \\
  ${window.location.protocol}//${window.location.host}/predict/${flowId}`;
};

/**
 * Function to get the python code for the API
 * @param {string} flowName - The name of the flow
 * @returns {string} - The python code
 */
export const getPythonCode = (flowName: string): string => {
  return `from langflow import load_flow_from_json

    flow = load_flow_from_json("${flowName}.json")
    # Now you can use it like any chain
    flow("Hey, have you heard of LangFlow?")`;
};
