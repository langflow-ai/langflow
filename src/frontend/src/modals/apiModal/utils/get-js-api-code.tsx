import { customGetHostProtocol } from "@/customization/utils/custom-get-host-protocol";
import { hasChatInputFiles, hasFileTweaks, getChatInputNodeId, getFileNodeId } from "./detect-file-tweaks";

/**
 * Generates JavaScript code for making API calls to a Langflow endpoint.
 *
 * @param {Object} params - The parameters for generating the API code
 * @param {string} params.flowId - The ID of the flow to run
 * @param {string} params.endpointName - The endpoint name for the flow
 * @param {Object} params.processedPayload - The pre-processed payload object
 * @param {boolean} params.isAuth - Whether authentication is required
 * @returns {string} Generated JavaScript code as a string
 */
export function getNewJsApiCode({
  flowId,
  endpointName,
  processedPayload,
  isAuth,
}: {
  flowId: string;
  endpointName: string;
  processedPayload: any;
  isAuth?: boolean;
}): string {
  const { protocol, host } = customGetHostProtocol();
  const baseUrl = `${protocol}//${host}`;

  // Check if there are file uploads
  const tweaks = processedPayload.tweaks || {};
  const hasFiles = hasFileTweaks(tweaks);
  const hasChatFiles = hasChatInputFiles(tweaks);

  // If no file uploads, use existing logic
  if (!hasFiles) {
    const apiUrl = `${baseUrl}/api/v1/run/${endpointName || flowId}`;

    // Add session_id to payload
    const payloadWithSession = {
      ...processedPayload,
      session_id: "user_1", // Optional: Use session tracking if needed
    };

    const payloadString = JSON.stringify(payloadWithSession, null, 4);

    const authSection = isAuth
      ? `// Get API key from environment variable
if (!process.env.LANGFLOW_API_KEY) {
    throw new Error('LANGFLOW_API_KEY environment variable not found. Please set your API key in the environment variables.');
}

`
      : "";

    const headersSection = isAuth
      ? `    headers: {
        'Content-Type': 'application/json',
        "x-api-key": process.env.LANGFLOW_API_KEY
    },`
      : `    headers: {
        'Content-Type': 'application/json'
    },`;

    return `${authSection}const payload = ${payloadString};

const options = {
    method: 'POST',
${headersSection}
    body: JSON.stringify(payload)
};

fetch('${apiUrl}', options)
    .then(response => response.json())
    .then(response => console.log(response))
    .catch(err => console.error(err));`;
  }

  // File upload logic
  if (hasChatFiles) {
    // Chat Input files - use v1 upload API + run endpoint with tweaks
    const chatInputNodeId = getChatInputNodeId(tweaks) || "ChatInput-NodeId";
    const authSection = isAuth
      ? `// Get API key from environment variable
if (!process.env.LANGFLOW_API_KEY) {
    throw new Error('LANGFLOW_API_KEY environment variable not found. Please set your API key in the environment variables.');
}

`
      : "";

    const headersCondition = isAuth
      ? `process.env.LANGFLOW_API_KEY ? {"x-api-key": process.env.LANGFLOW_API_KEY} : {}`
      : `{}`;

    return `${authSection}const BASE_URL = "${baseUrl}";
const FLOW_ID = "${flowId}";

async function uploadAndExecuteFlow() {
    try {
        // Step 1: Upload file for Chat Input
        const formData = new FormData();
        formData.append('file', document.getElementById('fileInput').files[0]); // Assuming file input element
        
        const headers = ${headersCondition};
        
        const uploadResponse = await fetch(\`\${BASE_URL}/api/v1/files/upload/\${FLOW_ID}\`, {
            method: 'POST',
            headers: headers,
            body: formData
        });
        
        if (!uploadResponse.ok) throw new Error('Upload failed');
        const uploadData = await uploadResponse.json();
        const filePath = uploadData.file_path;
        
        // Step 2: Execute flow
        const payload = {
            "output_type": "${processedPayload.output_type || "chat"}",
            "input_type": "${processedPayload.input_type || "chat"}",
            "input_value": "${processedPayload.input_value || "Your message here"}",
            "tweaks": {
                "${chatInputNodeId}": {
                    "files": filePath
                }
            }
        };
        
        const executeResponse = await fetch(\`\${BASE_URL}/api/v1/run/\${FLOW_ID}?stream=false\`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...headers
            },
            body: JSON.stringify(payload)
        });
        
        if (!executeResponse.ok) throw new Error('Execution failed');
        const result = await executeResponse.json();
        console.log(result);
        
    } catch (error) {
        console.error('Error:', error);
    }
}

uploadAndExecuteFlow();`;
  } else {
    // File/VideoFile components - use v2 upload API + run endpoint
    const fileNodeId = getFileNodeId(tweaks) || "File-NodeId";
    const authSection = isAuth
      ? `// Get API key from environment variable
if (!process.env.LANGFLOW_API_KEY) {
    throw new Error('LANGFLOW_API_KEY environment variable not found. Please set your API key in the environment variables.');
}

`
      : "";

    const headersCondition = isAuth
      ? `process.env.LANGFLOW_API_KEY ? {"x-api-key": process.env.LANGFLOW_API_KEY} : {}`
      : `{}`;

    return `${authSection}const BASE_URL = "${baseUrl}";
const FLOW_ID = "${flowId}";

async function uploadAndExecuteFlow() {
    try {
        // Step 1: Upload file
        const formData = new FormData();
        formData.append('file', document.getElementById('fileInput').files[0]); // Assuming file input element
        
        const headers = ${headersCondition};
        
        const uploadResponse = await fetch(\`\${BASE_URL}/api/v2/files\`, {
            method: 'POST',
            headers: headers,
            body: formData
        });
        
        if (!uploadResponse.ok) throw new Error('Upload failed');
        const uploadData = await uploadResponse.json();
        const fileId = uploadData.id;
        
        // Step 2: Run flow with file_id
        const payload = {
            "tweaks": {
                "${fileNodeId}": {
                    "file_id": fileId
                }
            }
        };
        
        const executeResponse = await fetch(\`\${BASE_URL}/api/v1/run/\${FLOW_ID}\`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...headers
            },
            body: JSON.stringify(payload)
        });
        
        if (!executeResponse.ok) throw new Error('Execution failed');
        const result = await executeResponse.json();
        console.log(result);
        
    } catch (error) {
        console.error('Error:', error);
    }
}

uploadAndExecuteFlow();`;
  }
}
