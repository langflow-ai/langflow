import { customGetHostProtocol } from "@/customization/utils/custom-get-host-protocol";
import {
  buildBasePayload,
  collectTweaksKeys,
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

  // Use shared utilities for consistent payload handling
  const tweaksKeys = collectTweaksKeys(tweaksObject, activeTweaks);
  const basePayload = buildBasePayload(
    tweaksKeys,
    input_value,
    input_type,
    output_type,
    true,
  ); // Include session_id for JS
  const tweaksString = getFormattedTweaksString(
    tweaksObject,
    activeTweaks,
    "javascript",
    4,
  );

  // Generate payload entries for JavaScript object
  const payloadEntries = Object.entries(basePayload).map(([key, value]) => {
    const comment =
      key === "input_value"
        ? " // The input value to be processed by the flow"
        : key === "output_type"
          ? " // Specifies the expected output format"
          : key === "input_type"
            ? " // Specifies the input format"
            : key === "session_id"
              ? " // Optional: Use session tracking if needed"
              : "";
    return `    "${key}": "${value}"${comment}`;
  });

  const hasTweaks = activeTweaks && tweaksObject;
  const payloadString =
    payloadEntries.length > 0
      ? payloadEntries
          .map((entry, index) => {
            const needsComma = hasTweaks || index < payloadEntries.length - 1;
            return `${entry}${needsComma ? "," : ""}`;
          })
          .join("\n")
      : "";

  const tweaksLine = hasTweaks
    ? `${payloadEntries.length > 0 ? ",\n" : ""}    "tweaks": ${tweaksString}`
    : "";

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
