/**
 * Function to get the curl code for the API
 * @param {string} flowId - The id of the flow
 * @param {boolean} isAuth - If the API is authenticated
 * @returns {string} - The curl code
 */
export default function getCurlCode(
  flowId: string,
  isAuth: boolean,
  tweaksBuildedObject,
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
