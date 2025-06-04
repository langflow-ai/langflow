import { customGetHostProtocol } from "@/customization/utils/custom-get-host-protocol";
import {
  buildBasePayload,
  buildPayloadString,
  generatePayloadEntries,
  generateTweaksLine,
  getFormattedTweaksString,
} from "./payload-utils";

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
 * @param {string} params.endpointName - The endpoint name for the flow
 * @param {Set<string>} params.excludedFields - Fields to exclude from base payload
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
  excludedFields,
}: {
  flowId: string;
  isAuthenticated: boolean;
  input_value: string;
  input_type: string;
  output_type: string;
  tweaksObject: any;
  activeTweaks: boolean;
  endpointName: string;
  excludedFields?: Set<string>;
}): string {
  const { protocol, host } = customGetHostProtocol();
  const apiUrl = `${protocol}//${host}/api/v1/run/${endpointName || flowId}`;

  // Use improved payload building logic that considers node types
  const basePayload = buildBasePayload(
    tweaksObject,
    activeTweaks,
    input_value,
    input_type,
    output_type,
    true, // Include session_id for JS
    excludedFields,
  );

  const tweaksString = getFormattedTweaksString(
    tweaksObject,
    activeTweaks,
    "javascript",
    4,
  );

  // Generate payload using utility functions
  const payloadEntries = generatePayloadEntries(basePayload, "javascript");
  const hasTweaks = activeTweaks && tweaksObject;
  const hasPayloadEntries = payloadEntries.length > 0;

  const payloadString = buildPayloadString(
    payloadEntries,
    hasTweaks,
    "javascript",
  );
  const tweaksLine = generateTweaksLine(
    hasTweaks,
    hasPayloadEntries,
    tweaksString,
    "javascript",
  );

  return `${
    isAuthenticated
      ? `// Get API key from environment variable
if (!process.env.LANGFLOW_API_KEY) {
    throw new Error('LANGFLOW_API_KEY environment variable not found. Please set your API key in the environment variables.');
}
`
      : ""
  }const payload = {
${payloadString}${tweaksLine}
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
