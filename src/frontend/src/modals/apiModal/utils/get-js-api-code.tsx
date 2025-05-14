import { customGetHostProtocol } from "@/customization/utils/custom-get-host-protocol";
import useFlowStore from "@/stores/flowStore";
import { GetCodeType } from "@/types/tweaks";

/**
 * Function to generate JavaScript code for interfacing with an API using the LangflowClient class.
 * @param {string} flowId - The id of the flow.
 * @param {boolean} isAuth - Whether the API requires authentication.
 * @param {any[]} tweaksBuildedObject - Customizations applied to the flow.
 * @param {string} [endpointName] - Optional endpoint name.
 * @returns {string} - The JavaScript code as a string.
 */
export default function getJsApiCode({
  flowId,
  isAuth,
  tweaksBuildedObject,
  endpointName,
  activeTweaks,
}: GetCodeType): string {
  let tweaksString = "{}";
  if (tweaksBuildedObject)
    tweaksString = JSON.stringify(tweaksBuildedObject, null, 8);
  const inputs = useFlowStore.getState().inputs;
  const outputs = useFlowStore.getState().outputs;
  const hasChatInput = inputs.some((input) => input.type === "ChatInput");
  const hasChatOutput = outputs.some((output) => output.type === "ChatOutput");

  const { protocol, host } = customGetHostProtocol();

  return `${activeTweaks ? "" : 'let inputValue = ""; // Insert input value here\n\n'}fetch(
  "${protocol}//${host}/api/v1/run/${endpointName || flowId}?stream=false",
  {
    method: "POST",
    headers: {
      "Authorization": "Bearer <TOKEN>",
      "Content-Type": "application/json",${isAuth ? '\n\t\t\t"x-api-key": <your api key>' : ""}
    },
    body: JSON.stringify({${activeTweaks ? "" : "\n\t\t\tinput_value: inputValue, "}
      output_type: ${hasChatOutput ? '"chat"' : '"text"'},
      input_type: ${hasChatInput ? '"chat"' : '"text"'},
      tweaks: ${tweaksString}
    }),
  },
)
  .then(res => res.json())
  .then(data => console.log(data))
  .catch(error => console.error('Error:', error));
`;
}
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

  const tweaksString =
    tweaksObject && activeTweaks ? JSON.stringify(tweaksObject, null, 2) : "{}";

  return `${
    isAuthenticated
      ? `// Get API key from environment variable
if (!process.env.LANGFLOW_API_KEY) {
    throw new Error('LANGFLOW_API_KEY environment variable not found. Please set your API key in the environment variables.');
}
`
      : ""
  }const payload = {
    "input_value": "${input_value}",
    "output_type": "${output_type}",
    "input_type": "${input_type}",
    // Optional: Use session tracking if needed
    "session_id": "user_1"${
      activeTweaks && tweaksObject
        ? `,
    "tweaks": ${tweaksString}`
        : ""
    }
};

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
    .catch(err => console.error(err));
    `;
}
