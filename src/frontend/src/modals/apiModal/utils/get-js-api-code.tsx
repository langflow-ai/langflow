import { customGetHostProtocol } from "@/customization/utils/custom-get-host-protocol";

/**
 * Generates JavaScript code for making API calls to a Langflow endpoint.
 *
 * @param {Object} params - The parameters for generating the API code
 * @param {string} params.flowId - The ID of the flow to run
 * @param {string} params.endpointName - The endpoint name for the flow
 * @param {Object} params.processedPayload - The pre-processed payload object
 * @returns {string} Generated JavaScript code as a string
 */
export function getNewJsApiCode({
  flowId,
  endpointName,
  processedPayload,
}: {
  flowId: string;
  endpointName: string;
  processedPayload: any;
}): string {
  const { protocol, host } = customGetHostProtocol();
  const apiUrl = `${protocol}//${host}/api/v1/run/${endpointName || flowId}`;

  // Add session_id to payload
  const payloadWithSession = {
    ...processedPayload,
    session_id: "user_1", // Optional: Use session tracking if needed
  };

  const payloadString = JSON.stringify(payloadWithSession, null, 4);

  return `// Get API key from environment variable
if (!process.env.LANGFLOW_API_KEY) {
    throw new Error('LANGFLOW_API_KEY environment variable not found. Please set your API key in the environment variables.');
}

const payload = ${payloadString};

const options = {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',\n        "x-api-key": process.env.LANGFLOW_API_KEY
    },
    body: JSON.stringify(payload)
};

fetch('${apiUrl}', options)
    .then(response => response.json())
    .then(response => console.log(response))
    .catch(err => console.error(err));`;
}
