import { customGetHostProtocol } from "@/customization/utils/custom-get-host-protocol";
import {
  getAllChatInputNodeIds,
  getAllFileNodeIds,
  getChatInputNodeId,
  getFileNodeId,
  getNonFileTypeTweaks,
  hasChatInputFiles,
  hasFileTweaks,
} from "./detect-file-tweaks";

/** Generates Node.js code for API calls, with multi-step file uploads (v1 for ChatInput, v2 for File/VideoFile) using http module, then flow execution. Handles auth. */
export function getNewJsApiCode({
  flowId,
  endpointName,
  processedPayload,
  shouldDisplayApiKey,
}: {
  flowId: string;
  endpointName: string;
  processedPayload: any;
  shouldDisplayApiKey: boolean;
}): string {
  const { protocol, host } = customGetHostProtocol();
  const baseUrl = `${protocol}//${host}`;

  // Parse URL for robust hostname/port extraction
  const parsedUrl = new URL(baseUrl);
  const hostname = parsedUrl.hostname;
  const port =
    parsedUrl.port || (parsedUrl.protocol === "https:" ? "443" : "80");

  // Check if there are file uploads
  const tweaks = processedPayload.tweaks || {};
  const hasFiles = hasFileTweaks(tweaks);

  // If no file uploads, use existing logic
  if (!hasFiles) {
    const apiUrl = `${baseUrl}/api/v1/run/${endpointName || flowId}`;

    const payloadString = JSON.stringify(processedPayload, null, 4);

    const authSection = shouldDisplayApiKey
      ? `const crypto = require('crypto');
const apiKey = 'YOUR_API_KEY_HERE';
`
      : "";

    const headersSection = shouldDisplayApiKey
      ? `    headers: {
        'Content-Type': 'application/json',
        "x-api-key": apiKey
    },`
      : "";

    return `${authSection}const payload = ${payloadString};
payload.session_id = crypto.randomUUID();

const options = {
    method: 'POST',
${headersSection}
    body: JSON.stringify(payload)
};

fetch('${apiUrl}', options)
    .then(response => response.json())
    .then(response => console.warn(response))
    .catch(err => console.error(err));`;
  }

  // File upload logic - handle multiple file types additively
  const chatInputNodeIds = getAllChatInputNodeIds(tweaks);
  const fileNodeIds = getAllFileNodeIds(tweaks);
  const nonFileTweaks = getNonFileTypeTweaks(tweaks);

  if (chatInputNodeIds.length === 0 && fileNodeIds.length === 0) {
    return getNewJsApiCode({
      flowId,
      endpointName,
      processedPayload: { ...processedPayload, tweaks: nonFileTweaks },
      shouldDisplayApiKey,
    });
  }

  const authSection = shouldDisplayApiKey
    ? `const apiKey = 'YOUR_API_KEY_HERE';
const authHeaders = { 'x-api-key': apiKey };`
    : "";

  // Build upload steps for each file component
  const uploadSteps: string[] = [];
  const resultVariables: string[] = [];
  const tweakEntries: string[] = [];

  // ChatInput files (v1 API)
  chatInputNodeIds.forEach((nodeId, index) => {
    const varName = `chatFilePath${index + 1}`;
    resultVariables.push(varName);

    uploadSteps.push(`        // Step ${
      uploadSteps.length + 1
    }: Upload file for ChatInput ${nodeId}
        const { payload: chatPayload${index + 1}, boundary: chatBoundary${
          index + 1
        } } = createFormData('your_image_${index + 1}.jpg');

        const chatUploadOptions${index + 1} = {
            hostname: '${hostname}',
            port: ${port},
            path: \`/api/v1/files/upload/\${FLOW_ID}\`,
            method: 'POST',
            headers: {
                'Content-Type': \`multipart/form-data; boundary=\${chatBoundary${
                  index + 1
                }}\`,
                'Content-Length': chatPayload${index + 1}.length,
                ...authHeaders
            }
        };

        const chatUploadResult${
          index + 1
        } = await makeRequest(chatUploadOptions${index + 1}, chatPayload${
          index + 1
        });
        const ${varName} = chatUploadResult${index + 1}.file_path;
        console.log('ChatInput upload ${
          index + 1
        } successful! File path:', ${varName});`);

    const originalTweak = tweaks[nodeId];
    const modifiedTweak = { ...originalTweak };
    modifiedTweak.files = [varName];
    tweakEntries.push(
      `            "${nodeId}": ${JSON.stringify(modifiedTweak, null, 12)
        .split("\n")
        .join("\n            ")}`,
    );
  });

  // File/VideoFile components (v2 API)
  fileNodeIds.forEach((nodeId, index) => {
    const varName = `filePath${index + 1}`;
    resultVariables.push(varName);

    uploadSteps.push(`        // Step ${
      uploadSteps.length + 1
    }: Upload file for File/VideoFile ${nodeId}
        const { payload: filePayload${index + 1}, boundary: fileBoundary${
          index + 1
        } } = createFormData('your_file_${index + 1}.pdf');

        const fileUploadOptions${index + 1} = {
            hostname: '${hostname}',
            port: ${port},
            path: '/api/v2/files',
            method: 'POST',
            headers: {
                'Content-Type': \`multipart/form-data; boundary=\${fileBoundary${
                  index + 1
                }}\`,
                'Content-Length': filePayload${index + 1}.length,
                ...authHeaders
            }
        };

        const fileUploadResult${
          index + 1
        } = await makeRequest(fileUploadOptions${index + 1}, filePayload${
          index + 1
        });
        const ${varName} = fileUploadResult${index + 1}.path;
        console.log('File upload ${
          index + 1
        } successful! File path:', ${varName});`);

    const originalTweak = tweaks[nodeId];
    const modifiedTweak = { ...originalTweak };
    if ("path" in originalTweak) {
      modifiedTweak.path = [varName];
    } else if ("file_path" in originalTweak) {
      modifiedTweak.file_path = varName;
    }
    tweakEntries.push(
      `            "${nodeId}": ${JSON.stringify(modifiedTweak, null, 12)
        .split("\n")
        .join("\n            ")}`,
    );
  });

  // Add non-file tweaks
  Object.entries(nonFileTweaks).forEach(([nodeId, tweak]) => {
    tweakEntries.push(
      `            "${nodeId}": ${JSON.stringify(tweak, null, 12)
        .split("\n")
        .join("\n            ")}`,
    );
  });

  const allTweaks = tweakEntries.length > 0 ? tweakEntries.join(",\n") : "";

  return `${authSection}const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const BASE_URL = "${baseUrl}";
const FLOW_ID = "${flowId}";
const protocol = new URL(BASE_URL).protocol;
const httpModule = protocol === 'https:' ? require('https') : require('http');

// Helper function to create multipart form data
function createFormData(filePath) {
    const boundary = '----FormBoundary' + Date.now();
    const filename = path.basename(filePath);

    if (!fs.existsSync(filePath)) {
        throw new Error(\`File not found: \${filePath}\`);
    }

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
        const req = httpModule.request(options, (res) => {
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
    try {${
      shouldDisplayApiKey
        ? `
        const apiKey = 'YOUR_API_KEY_HERE';
        const authHeaders = { 'x-api-key': apiKey };`
        : `
        const authHeaders = {};`
    }

${uploadSteps.join("\n\n")}

        // Step ${uploadSteps.length + 1}: Execute flow with all file paths
        const executePayload = JSON.stringify({
            "output_type": "${processedPayload.output_type || "chat"}",
            "input_type": "${processedPayload.input_type || "chat"}",
            "input_value": "${
              processedPayload.input_value || "Your message here"
            }",
            "session_id": crypto.randomUUID(),
            "tweaks": {
${allTweaks}
            }
        });

        const executeOptions = {
            hostname: '${hostname}',
            port: ${port},
            path: \`/api/v1/run/${endpointName || flowId}\`,
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(executePayload),
                ...authHeaders
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
