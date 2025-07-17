import { ENABLE_DATASTAX_LANGFLOW } from "@/customization/feature-flags";
import { customGetHostProtocol } from "@/customization/utils/custom-get-host-protocol";
import { GetCodeType } from "@/types/tweaks";
import {
  getAllChatInputNodeIds,
  getAllFileNodeIds,
  getNonFileTypeTweaks,
  hasFileTweaks,
} from "./detect-file-tweaks";

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

/** Generates Curl command for API calls, handling multi-step file uploads (v1 API for ChatInput files, v2 for File/VideoFile) before execution if tweaks contain files. Supports Unix/PowerShell and optional auth. */
export function getNewCurlCode({
  flowId,
  endpointName,
  processedPayload,
  platform,
}: {
  flowId: string;
  endpointName: string;
  processedPayload: any;
  platform?: "unix" | "powershell";
}): { steps: { title: string; code: string }[] } | string {
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

  // If no file uploads, use existing logic
  if (!hasFiles) {
    if (detectedPlatform === "powershell") {
      const payloadWithSession = {
        ...processedPayload,
        session_id: "YOUR_SESSION_ID_HERE",
      };
      const singleLinePayload = JSON.stringify(payloadWithSession);
      // PowerShell with here-string (most robust for complex JSON)
      const authHeader = `     --header "x-api-key: YOUR_API_KEY_HERE" \``;

      return `$jsonData = @'
${singleLinePayload}
'@

curl.exe --request POST \`
     --url "${apiUrl}?stream=false" \`
     --header "Content-Type: application/json" \`${authHeader ? "\n" + authHeader : ""}
     --data $jsonData`;
    } else {
      const payloadWithSession = {
        ...processedPayload,
        session_id: "YOUR_SESSION_ID_HERE",
      };
      // Unix-like systems (Linux, Mac, WSL2)
      const unixFormattedPayload = JSON.stringify(payloadWithSession, null, 2)
        .split("\n")
        .map((line, index) => (index === 0 ? line : "         " + line))
        .join("\n\t\t");

      const authHeader = `     --header "x-api-key: YOUR_API_KEY_HERE" \\ `;

      return `curl --request POST \\
     --url '${apiUrl}?stream=false' \\
     --header 'Content-Type: application/json' \\${authHeader ? "\n" + authHeader : ""}
     --data '${unixFormattedPayload}'`;
    }
  }

  // File upload logic - handle multiple file types additively
  const chatInputNodeIds = getAllChatInputNodeIds(tweaks);
  const fileNodeIds = getAllFileNodeIds(tweaks);
  const nonFileTweaks = getNonFileTypeTweaks(tweaks);

  // Build upload commands and tweak entries
  const uploadCommands: string[] = [];
  const tweakEntries: string[] = [];
  let uploadCounter = 1;

  // Add ChatInput file uploads (v1 API)
  chatInputNodeIds.forEach((nodeId, index) => {
    if (detectedPlatform === "powershell") {
      uploadCommands.push(
        `curl.exe --request POST \`
     --url "${baseUrl}/api/v1/files/upload/${flowId}" \`
     --header "x-api-key: YOUR_API_KEY_HERE" \`
     --form "file=@your_image_${uploadCounter}.jpg"`,
      );
    } else {
      uploadCommands.push(
        `curl --request POST \\
     --url "${baseUrl}/api/v1/files/upload/${flowId}" \\
     --header "x-api-key: YOUR_API_KEY_HERE" \\
     --form "file=@your_image_${uploadCounter}.jpg"`,
      );
    }
    const originalTweak = tweaks[nodeId];
    const modifiedTweak = { ...originalTweak };
    modifiedTweak.files = `REPLACE_WITH_FILE_PATH_FROM_UPLOAD_${uploadCounter}`;
    const tweakEntry = `    "${nodeId}": ${JSON.stringify(modifiedTweak, null, 6).split("\n").join("\n    ")}`;
    tweakEntries.push(tweakEntry);
    uploadCounter++;
  });

  // Add File/VideoFile uploads (v2 API)
  fileNodeIds.forEach((nodeId, index) => {
    if (detectedPlatform === "powershell") {
      uploadCommands.push(
        `curl.exe --request POST \`
     --url "${baseUrl}/api/v2/files" \`
     --header "x-api-key: YOUR_API_KEY_HERE" \`
     --form "file=@your_file_${uploadCounter}.pdf"`,
      );
    } else {
      uploadCommands.push(
        `curl --request POST \\
     --url "${baseUrl}/api/v2/files" \\
     --header "x-api-key: YOUR_API_KEY_HERE" \\
     --form "file=@your_file_${uploadCounter}.pdf"`,
      );
    }
    const originalTweak = tweaks[nodeId];
    const modifiedTweak = { ...originalTweak };
    if ("path" in originalTweak) {
      modifiedTweak.path = [
        `REPLACE_WITH_FILE_PATH_FROM_UPLOAD_${uploadCounter}`,
      ];
    } else if ("file_path" in originalTweak) {
      modifiedTweak.file_path = `REPLACE_WITH_FILE_PATH_FROM_UPLOAD_${uploadCounter}`;
    }
    const tweakEntry = `    "${nodeId}": ${JSON.stringify(modifiedTweak, null, 6).split("\n").join("\n    ")}`;
    tweakEntries.push(tweakEntry);
    uploadCounter++;
  });

  // Add non-file tweaks
  Object.entries(nonFileTweaks).forEach(([nodeId, tweak]) => {
    tweakEntries.push(
      `    "${nodeId}": ${JSON.stringify(tweak, null, 6).split("\n").join("\n    ")}`,
    );
  });

  const allTweaks = tweakEntries.length > 0 ? tweakEntries.join(",\n") : "";

  if (detectedPlatform === "powershell") {
    const authHeader = ` -H "x-api-key: YOUR_API_KEY_HERE"`;

    const uploadStep = uploadCommands.join("\n");
    const executeStep = `curl.exe -X POST "${apiUrl}" -H "Content-Type: application/json"${authHeader} -d '{
  "output_type": "${processedPayload.output_type || "chat"}",
  "input_type": "${processedPayload.input_type || "chat"}",
  "input_value": "${processedPayload.input_value || "Your message here"}",
  "session_id": "YOUR_SESSION_ID_HERE",
  "tweaks": {
${allTweaks}
  }
}'`;

    // Return structured steps instead of concatenated string
    return {
      steps: [
        { title: "Upload files to the server", code: uploadStep },
        { title: "Execute the flow with uploaded files", code: executeStep },
      ],
    };
  } else {
    const authHeader = ` -H "x-api-key: YOUR_API_KEY_HERE"`;

    const uploadStep = uploadCommands.join("\n");
    const executeStep = `curl -X POST \\
  "${apiUrl}" \\
  -H "Content-Type: application/json"${authHeader ? " \\\n " + authHeader : ""} \\
  -d '{\n    "output_type": "${processedPayload.output_type || "chat"}",\n    "input_type": "${processedPayload.input_type || "chat"}",\n    "input_value": "${processedPayload.input_value || "Your message here"}",\n    "session_id": "YOUR_SESSION_ID_HERE",\n    "tweaks": {\n${allTweaks}\n    }\n  }'`;

    // Return structured steps instead of concatenated string
    return {
      steps: [
        { title: "Upload files to the server", code: uploadStep },
        { title: "Execute the flow with uploaded files", code: executeStep },
      ],
    };
  }
}
