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

    return `${authSection}const fs = require('fs');
const http = require('http');
const path = require('path');

const BASE_URL = "${baseUrl}";
const FLOW_ID = "${flowId}";

// Helper function to create multipart form data
function createFormData(filePath) {
    const boundary = '----FormBoundary' + Date.now();
    const filename = path.basename(filePath);
    const fileData = fs.readFileSync(filePath);
    
    let data = '';
    data += \`--\${boundary}\\r\\n\`;
    data += \`Content-Disposition: form-data; name="file"; filename="\${filename}"\\r\\n\`;
    data += \`Content-Type: image/jpeg\\r\\n\\r\\n\`;
    
    const payload = Buffer.concat([
        Buffer.from(data, 'utf8'),
        fileData,
        Buffer.from(\`\\r\\n--\${boundary}--\\r\\n\`, 'utf8')
    ]);
    
    return { payload, boundary };
}

// Helper function to make HTTP requests
function makeRequest(options, data) {
    return new Promise((resolve, reject) => {
        const req = http.request(options, (res) => {
            let responseData = '';
            res.on('data', (chunk) => { responseData += chunk; });
            res.on('end', () => {
                if (res.statusCode >= 200 && res.statusCode < 300) {
                    try {
                        resolve(JSON.parse(responseData));
                    } catch (e) {
                        resolve(responseData);
                    }
                } else {
                    reject(new Error(\`Request failed with status \${res.statusCode}: \${responseData}\`));
                }
            });
        });
        req.on('error', reject);
        if (data) req.write(data);
        req.end();
    });
}

async function uploadAndExecuteFlow() {
    try {
        // Step 1: Upload file for Chat Input
        const { payload, boundary } = createFormData('your-image.jpg');
        ${isAuth ? `
        const authHeaders = process.env.LANGFLOW_API_KEY ? 
            { 'x-api-key': process.env.LANGFLOW_API_KEY } : {};` : ''}
        
        const uploadOptions = {
            hostname: '${host.split(':')[0]}',
            port: ${host.includes(':') ? host.split(':')[1] : (protocol === 'https:' ? '443' : '80')},
            path: \`/api/v1/files/upload/\${FLOW_ID}\`,
            method: 'POST',
            headers: {
                'Content-Type': \`multipart/form-data; boundary=\${boundary}\`,
                'Content-Length': payload.length${isAuth ? `,
                ...authHeaders` : ''}
            }
        };
        
        const uploadResult = await makeRequest(uploadOptions, payload);
        const filePath = uploadResult.file_path;
        console.log('Upload successful! File path:', filePath);
        
        // Step 2: Execute flow
        const executePayload = JSON.stringify({
            "output_type": "${processedPayload.output_type || "chat"}",
            "input_type": "${processedPayload.input_type || "chat"}",
            "input_value": "${processedPayload.input_value || "Your message here"}",
            "tweaks": {
                "${chatInputNodeId}": {
                    "files": filePath
                }
            }
        });
        
        const executeOptions = {
            hostname: '${host.split(':')[0]}',
            port: ${host.includes(':') ? host.split(':')[1] : (protocol === 'https:' ? '443' : '80')},
            path: \`/api/v1/run/\${FLOW_ID}?stream=false\`,
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(executePayload)${isAuth ? `,
                ...authHeaders` : ''}
            }
        };
        
        const result = await makeRequest(executeOptions, executePayload);
        console.log('Flow execution successful!');
        console.log(result);
        
    } catch (error) {
        console.error('Error:', error.message);
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

    return `${authSection}const fs = require('fs');
const http = require('http');
const path = require('path');

const BASE_URL = "${baseUrl}";
const FLOW_ID = "${flowId}";

// Helper function to create multipart form data
function createFormData(filePath) {
    const boundary = '----FormBoundary' + Date.now();
    const filename = path.basename(filePath);
    const fileData = fs.readFileSync(filePath);
    
    let data = '';
    data += \`--\${boundary}\\r\\n\`;
    data += \`Content-Disposition: form-data; name="file"; filename="\${filename}"\\r\\n\`;
    data += \`Content-Type: application/octet-stream\\r\\n\\r\\n\`;
    
    const payload = Buffer.concat([
        Buffer.from(data, 'utf8'),
        fileData,
        Buffer.from(\`\\r\\n--\${boundary}--\\r\\n\`, 'utf8')
    ]);
    
    return { payload, boundary };
}

// Helper function to make HTTP requests
function makeRequest(options, data) {
    return new Promise((resolve, reject) => {
        const req = http.request(options, (res) => {
            let responseData = '';
            res.on('data', (chunk) => { responseData += chunk; });
            res.on('end', () => {
                if (res.statusCode >= 200 && res.statusCode < 300) {
                    try {
                        resolve(JSON.parse(responseData));
                    } catch (e) {
                        resolve(responseData);
                    }
                } else {
                    reject(new Error(\`Request failed with status \${res.statusCode}: \${responseData}\`));
                }
            });
        });
        req.on('error', reject);
        if (data) req.write(data);
        req.end();
    });
}

async function uploadAndExecuteFlow() {
    try {
        // Step 1: Upload file
        const { payload, boundary } = createFormData('your-file.pdf');
        ${isAuth ? `
        const authHeaders = process.env.LANGFLOW_API_KEY ? 
            { 'x-api-key': process.env.LANGFLOW_API_KEY } : {};` : ''}
        
        const uploadOptions = {
            hostname: '${host.split(':')[0]}',
            port: ${host.includes(':') ? host.split(':')[1] : (protocol === 'https:' ? '443' : '80')},
            path: '/api/v2/files',
            method: 'POST',
            headers: {
                'Content-Type': \`multipart/form-data; boundary=\${boundary}\`,
                'Content-Length': payload.length${isAuth ? `,
                ...authHeaders` : ''}
            }
        };
        
        const uploadResult = await makeRequest(uploadOptions, payload);
        const fileId = uploadResult.id;
        console.log('Upload successful! File ID:', fileId);
        
        // Step 2: Run flow with file_id
        const executePayload = JSON.stringify({
            "tweaks": {
                "${fileNodeId}": {
                    "file_id": fileId
                }
            }
        });
        
        const executeOptions = {
            hostname: '${host.split(':')[0]}',
            port: ${host.includes(':') ? host.split(':')[1] : (protocol === 'https:' ? '443' : '80')},
            path: \`/api/v1/run/\${FLOW_ID}\`,
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(executePayload)${isAuth ? `,
                ...authHeaders` : ''}
            }
        };
        
        const result = await makeRequest(executeOptions, executePayload);
        console.log('Flow execution successful!');
        console.log(result);
        
    } catch (error) {
        console.error('Error:', error.message);
    }
}

uploadAndExecuteFlow();`;
  }
}
