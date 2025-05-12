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
    tweaksString = JSON.stringify(tweaksBuildedObject, null, 2)
      .replace(/^ {2}/gm, "    ")
      .replace(/}$/, "  }");
  const inputs = useFlowStore.getState().inputs;
  const outputs = useFlowStore.getState().outputs;
  const hasChatInput = inputs.some((input) => input.type === "ChatInput");
  const hasChatOutput = outputs.some((output) => output.type === "ChatOutput");

  return `import { LangflowClient } from "@datastax/langflow-client"; // Make sure to \`npm install @datastax/langflow-client\`

const client = new LangflowClient({
  baseUrl: "${window.location.protocol}//${window.location.host}"${isAuth ? ",\n  apiKey: <your api key>" : ""}
})
const flow = client.flow("${endpointName || flowId}");

let inputValue = ""; // Insert input value here

flow.run(inputValue, {
  output_type: ${hasChatOutput ? '"chat"' : '"text"'},
  input_type: ${hasChatInput ? '"chat"' : '"text"'},
  session_id: "user_1",
  tweaks: ${tweaksString}
}).then(response => {
  // get the text of the first chat response
  console.log(response.chatOutputText());
  // Or get all the outputs
  console.log(response.outputs);
}.catch(error => {
  console.error(error);
});`;
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
}: {
  flowId: string;
  isAuthenticated: boolean;
  input_value: string;
  input_type: string;
  output_type: string;
  tweaksObject: any;
  activeTweaks: boolean;
}): string {
  const host = window.location.host;
  const protocol = window.location.protocol;
  const apiUrl = `${protocol}//${host}/api/v1/run/${flowId}`;

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
