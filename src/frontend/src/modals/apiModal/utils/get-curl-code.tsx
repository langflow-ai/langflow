import { ENABLE_DATASTAX_LANGFLOW } from "@/customization/feature-flags";
import { customGetHostProtocol } from "@/customization/utils/custom-get-host-protocol";
import { GetCodeType } from "@/types/tweaks";
import { hasChatInputFiles, hasFileTweaks, getChatInputNodeId, getFileNodeId } from "./detect-file-tweaks";

/**
 * Generates a cURL command for making a POST request to a webhook endpoint.
 *
 * @param {Object} options - The options for generating the cURL command.
 * @param {string} options.flowId - The ID of the flow.
 * @param {boolean} options.isAuth - Indicates whether authentication is required.
 * @param {string} options.endpointName - The name of the webhook endpoint.
 * @returns {string} The cURL command.
 */
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
  endpointName,
  processedPayload,
  platform,
  isAuth,
}: {
  flowId: string;
  endpointName: string;
  processedPayload: any;
  platform?: "unix" | "powershell";
  isAuth?: boolean;
}): string {
  const { protocol, host } = customGetHostProtocol();
  const baseUrl = `${protocol}//${host}`;
  const apiUrl = `${baseUrl}/api/v1/run/${endpointName || flowId}`;

  // Auto-detect if no platform specified
  const detectedPlatform =
    platform ||
    (/Windows|Win32|Win64|WOW32|WOW64/i.test(navigator.userAgent)
      ? "powershell"
      : "unix");

  // Check if there are file uploads
  const tweaks = processedPayload.tweaks || {};
  const hasFiles = hasFileTweaks(tweaks);
  const hasChatFiles = hasChatInputFiles(tweaks);

  // If no file uploads, use existing logic
  if (!hasFiles) {
    const singleLinePayload = JSON.stringify(processedPayload);

    if (detectedPlatform === "powershell") {
      // PowerShell with here-string (most robust for complex JSON)
      const authCheck = isAuth
        ? `if (-not $env:LANGFLOW_API_KEY) {
    Write-Error "LANGFLOW_API_KEY environment variable not found"
    exit 1
}

`
        : "";
      const authHeader = isAuth
        ? `     --header "x-api-key: $env:LANGFLOW_API_KEY" \\`
        : "";

      return `${authCheck}$jsonData = @'
${singleLinePayload}
'@

curl --request POST \`
     --url "${apiUrl}?stream=false" \`
     --header "Content-Type: application/json" \`${authHeader ? "\n" + authHeader : ""}
     --data $jsonData`;
    } else {
      // Unix-like systems (Linux, Mac, WSL2)
      const unixFormattedPayload = JSON.stringify(processedPayload, null, 2)
        .split("\n")
        .map((line, index) => (index === 0 ? line : "         " + line))
        .join("\n\t\t");

      const authCheck = isAuth
        ? `# Get API key from environment variable
if [ -z "$LANGFLOW_API_KEY" ]; then
    echo "Error: LANGFLOW_API_KEY environment variable not found. Please set your API key in the environment variables."
    exit 1
fi

`
        : "";
      const authHeader = isAuth
        ? `     --header "x-api-key: $LANGFLOW_API_KEY" \\`
        : "";

      return `${authCheck}curl --request POST \\
     --url '${apiUrl}?stream=false' \\
     --header 'Content-Type: application/json' \\${authHeader ? "\n" + authHeader : ""}
     --data '${unixFormattedPayload}'`;
    }
  }

  // File upload logic
  if (hasChatFiles) {
    // Chat Input files - use v1 upload API + run endpoint with tweaks
    const chatInputNodeId = getChatInputNodeId(tweaks) || "ChatInput-NodeId";
    
    if (detectedPlatform === "powershell") {
      const authHeader = isAuth ? `-H "x-api-key: $env:LANGFLOW_API_KEY"` : "";

      return `##STEP1_START##
curl -X POST "${baseUrl}/api/v1/files/upload/${flowId}"${authHeader ? " " + authHeader : ""} -F "file=@your_image_path.jpg"
##STEP1_END##

##STEP2_START##
curl -X POST "${apiUrl}?stream=false" -H "Content-Type: application/json"${authHeader ? " " + authHeader : ""} -d '{
  "output_type": "${processedPayload.output_type || "chat"}",
  "input_type": "${processedPayload.input_type || "chat"}",
  "input_value": "${processedPayload.input_value || "Your message here"}",
  "tweaks": {
    "${chatInputNodeId}": {
      "files": "REPLACE_WITH_FILE_PATH_FROM_STEP_1"
    }
  }
}'
##STEP2_END##`;
    } else {
      const authHeader = isAuth ? `-H "x-api-key: $LANGFLOW_API_KEY"` : "";
      
      return `##STEP1_START##
curl -X POST "${baseUrl}/api/v1/files/upload/${flowId}"${authHeader ? " " + authHeader : ""} -F "file=@your_image_path.jpg"
##STEP1_END##

##STEP2_START##
curl -X POST \\
  "${apiUrl}?stream=false" \\
  -H "Content-Type: application/json"${authHeader ? " \\\n  " + authHeader : ""} \\
  -d '{
    "output_type": "${processedPayload.output_type || "chat"}",
    "input_type": "${processedPayload.input_type || "chat"}",
    "input_value": "${processedPayload.input_value || "Your message here"}",
    "tweaks": {
      "${chatInputNodeId}": {
        "files": "REPLACE_WITH_FILE_PATH_FROM_STEP_1"
      }
    }
  }'
##STEP2_END##`;
    }
  } else {
    // File/VideoFile components - use v2 upload API + run endpoint
    const fileNodeId = getFileNodeId(tweaks) || "File-NodeId";
    
    if (detectedPlatform === "powershell") {
      const authHeader = isAuth ? `-H "x-api-key: $env:LANGFLOW_API_KEY"` : "";

      return `##STEP1_START##
curl -X POST "${baseUrl}/api/v2/files"${authHeader ? " " + authHeader : ""} -F "file=@your_document_path.pdf"
##STEP1_END##

##STEP2_START##
curl -X POST "${apiUrl}" -H "Content-Type: application/json"${authHeader ? " " + authHeader : ""} -d '{
  "tweaks": {
    "${fileNodeId}": {
      "file_id": "REPLACE_WITH_FILE_ID_FROM_STEP_1"
    }
  }
}'
##STEP2_END##`;
    } else {
      const authHeader = isAuth ? `-H "x-api-key: $LANGFLOW_API_KEY"` : "";
      
      return `##STEP1_START##
curl -X POST "${baseUrl}/api/v2/files"${authHeader ? " " + authHeader : ""} -F "file=@your_document_path.pdf"
##STEP1_END##

##STEP2_START##
curl -X POST \\
  "${apiUrl}" \\
  -H "Content-Type: application/json"${authHeader ? " \\\n  " + authHeader : ""} \\
  -d '{
    "tweaks": {
      "${fileNodeId}": {
        "file_id": "REPLACE_WITH_FILE_ID_FROM_STEP_1"
      }
    }
  }'
##STEP2_END##`;
    }
  }
}
