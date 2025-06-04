import { customGetHostProtocol } from "@/customization/utils/custom-get-host-protocol";
import { formatPayloadTweaks } from "./filter-tweaks";

/**
 * Generates JavaScript code for making API calls to a Langflow endpoint.
 *
 * @param {Object} params - The parameters for generating the API code
 * @param {string} params.flowId - The ID of the flow to run
 * @param {boolean} params.isAuthenticated - Whether authentication is required
 * @param {string} params.input_value - The input value to send to the flow
 * @param {string} params.input_type - The type of input (e.g. "text", "chat")
 * @param {string} params.output_type - The type of output (e.g. "text", "chat")
 * @param {Object} params.tweaksObject - Optional tweaks to customize flow behavior
 * @param {boolean} params.activeTweaks - Whether tweaks should be included
 * @returns {string} Generated JavaScript code as a string
 */
export function getNewJsApiCode({
  flowId,
  isAuthenticated,
  input_value,
  input_type,
  output_type,
  tweaksObject,
  activeTweaks,
  endpointName,
}: {
  flowId: string;
  isAuthenticated: boolean;
  input_value: string;
  input_type: string;
  output_type: string;
  tweaksObject: any;
  activeTweaks: boolean;
  endpointName: string;
}): string {
  const { protocol, host } = customGetHostProtocol();
  const apiUrl = `${protocol}//${host}/api/v1/run/${endpointName || flowId}`;

  const includeTopLevelInputValue = formatPayloadTweaks(tweaksObject);

  const payloadObj: any = {
    output_type: output_type,
    input_type: input_type,
    session_id: "user_1", // Optional: Use session tracking if needed
  };

  if (includeTopLevelInputValue) {
    payloadObj.input_value = input_value;
  }

  if (activeTweaks && tweaksObject && Object.keys(tweaksObject).length > 0) {
    payloadObj.tweaks = tweaksObject;
  }

  const payloadString = JSON.stringify(payloadObj, null, 4);

  return `${
    isAuthenticated
      ? `// Get API key from environment variable
if (!process.env.LANGFLOW_API_KEY) {
    throw new Error('LANGFLOW_API_KEY environment variable not found. Please set your API key in the environment variables.');
}

`
      : ""
  }const payload = ${payloadString};

const options = {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json'${isAuthenticated ? ',\n        "x-api-key": process.env.LANGFLOW_API_KEY' : ""}
    },
    body: JSON.stringify(payload)
};

fetch('${apiUrl}', options)
    .then(response => response.json())
    .then(response => console.log(response))
    .catch(err => console.error(err));`;
}
