import { ENABLE_DATASTAX_LANGFLOW } from "@/customization/feature-flags";
import { customGetHostProtocol } from "@/customization/utils/custom-get-host-protocol";
import useFlowStore from "@/stores/flowStore";
import { GetCodeType } from "@/types/tweaks";

/**
 * Function to get the curl code for the API
 * @param {string} flowId - The id of the flow
 * @param {boolean} isAuth - If the API is authenticated
 * @returns {string} - The curl code
 */
export function getCurlRunCode({
  flowId,
  isAuth,
  tweaksBuildedObject,
  endpointName,
  activeTweaks,
}: GetCodeType): string {
  let tweaksString = "{}";
  const inputs = useFlowStore.getState().inputs;
  const outputs = useFlowStore.getState().outputs;
  const hasChatInput = inputs.some((input) => input.type === "ChatInput");
  const hasChatOutput = outputs.some((output) => output.type === "ChatOutput");
  if (tweaksBuildedObject)
    tweaksString = JSON.stringify(tweaksBuildedObject, null, 2);
  // show the endpoint name in the curl command if it exists

  const { protocol, host } = customGetHostProtocol();

  return `curl -X POST \\
    "${protocol}//${host}/api/v1/run/${endpointName || flowId}?stream=false" \\
    -H 'Content-Type: application/json'\\${
      !isAuth ? `\n  -H 'x-api-key: <your api key>'\\` : ""
    }
    -d '{${!activeTweaks ? `"input_value": "message",` : ""}
    "output_type": ${hasChatOutput ? '"chat"' : '"text"'},
    "input_type": ${hasChatInput ? '"chat"' : '"text"'},
    "tweaks": ${tweaksString}}'
    `;
}

/**
 * Generates a cURL command for making a POST request to a webhook endpoint.
 *
 * @param {Object} options - The options for generating the cURL command.
 * @param {string} options.flowId - The ID of the flow.
 * @param {boolean} options.isAuth - Indicates whether authentication is required.
 * @param {string} options.endpointName - The name of the webhook endpoint.
 * @returns {string} The cURL command.
 */

// KEEP THIS FOR LFOSS
export function getCurlWebhookCode({
  flowId,
  isAuth,
  endpointName,
  format = "multiline",
}: GetCodeType & { format?: "multiline" | "singleline" }) {
  const { protocol, host } = customGetHostProtocol();
  const baseUrl = `${protocol}//${host}/api/v1/webhook/${endpointName || flowId}`;
  const authHeader = !isAuth ? `-H 'x-api-key: <your api key>'` : "";

  if (format === "singleline") {
    return `curl -X POST "${baseUrl}" -H 'Content-Type: application/json' ${authHeader} -d '{"any": "data"}'`.trim();
  }

  return `curl -X POST \\
  "${baseUrl}" \\
  -H 'Content-Type: application/json' \\${
    isAuth ? `\n  -H 'x-api-key: <your api key>' \\` : ""
  }${
    ENABLE_DATASTAX_LANGFLOW
      ? `\n  -H 'Authorization: Bearer <YOUR_APPLICATION_TOKEN>' \\`
      : ""
  }
  -d '{"any": "data"}'
  `.trim();
}

export function getNewCurlCode({
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

  // Construct the payload
  const payload = {
    input_value: input_value,
    output_type: output_type,
    input_type: input_type,
    ...(activeTweaks && tweaksObject
      ? { tweaks: JSON.parse(tweaksString) }
      : {}),
  };

  return `${
    isAuthenticated
      ? `# Get API key from environment variable
if [ -z "$LANGFLOW_API_KEY" ]; then
  echo "Error: LANGFLOW_API_KEY environment variable not found. Please set your API key in the environment variables."
fi
`
      : ""
  }curl --request POST \\
  --url '${apiUrl}?stream=false' \\
  --header 'Content-Type: application/json' \\${
    isAuthenticated
      ? `
  --header "x-api-key: $LANGFLOW_API_KEY" \\`
      : ""
  }
  --data '${JSON.stringify(payload, null, 2)}'`;
}
