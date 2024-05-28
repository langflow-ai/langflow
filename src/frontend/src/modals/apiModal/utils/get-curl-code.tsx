/**
 * Function to get the curl code for the API
 * @param {string} flowId - The id of the flow
 * @param {boolean} isAuth - If the API is authenticated
 * @returns {string} - The curl code
 */
export default function getCurlRunCode(
  flowId: string,
  isAuth: boolean,
  tweaksBuildedObject
): string {
  const tweaksObject = tweaksBuildedObject[0];

  return `curl -X POST \\
    ${window.location.protocol}//${
    window.location.host
  }/api/v1/run/${flowId}?stream=false \\
    -H 'Content-Type: application/json'\\${
      !isAuth ? `\n  -H 'x-api-key: <your api key>'\\` : ""
    }
    -d '{"input_value": "message",
    "output_type": "chat",
    "input_type": "chat",
    "tweaks": ${JSON.stringify(tweaksObject, null, 2)}}'
    `;
}

/**
 * Generates a cURL command for making a POST request to a webhook endpoint.
 *
 * @param {Object} options - The options for generating the cURL command.
 * @param {string} options.flowId - The ID of the flow.
 * @param {boolean} options.isAuth - Indicates whether authentication is required.
 * @returns {string} The cURL command.
 */
export function getCurlWebhookCode(flowId, isAuth): string {
  return `curl -X POST \\
  ${window.location.protocol}//${
    window.location.host
  }/api/v1/webhook/${flowId} \\
  -H 'Content-Type: application/json'\\${
    !isAuth ? `\n  -H 'x-api-key: <your api key>'\\` : ""
  }
  -d '{"any": "data"}'
  `;
}
