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

/** Generates Python code using requests for API calls, handling multi-step file uploads (v1 for ChatInput, v2 for others) before flow execution. Supports auth. */
export function getNewPythonApiCode({
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

  // Check if there are file uploads
  const tweaks = processedPayload.tweaks || {};
  const hasFiles = hasFileTweaks(tweaks);

  // If no file uploads, use existing logic
  if (!hasFiles) {
    const apiUrl = `${baseUrl}/api/v1/run/${endpointName || flowId}`;
    const payloadString = JSON.stringify(processedPayload, null, 4)
      .replace(/true/g, "True")
      .replace(/false/g, "False")
      .replace(/null/g, "None");

    const authSection = shouldDisplayApiKey
      ? `api_key = 'YOUR_API_KEY_HERE'`
      : "";

    const headersSection = shouldDisplayApiKey
      ? `headers = {"x-api-key": api_key}`
      : "";

    return `import requests
import os
import uuid

${authSection}url = "${apiUrl}"  # The complete API endpoint URL for this flow

# Request payload configuration
payload = ${payloadString}
payload["session_id"] = str(uuid.uuid4())

${headersSection}

try:
    # Send API request
    response = requests.request("POST", url, json=payload, headers=headers)
    response.raise_for_status()  # Raise exception for bad status codes

    # Print response
    print(response.text)

except requests.exceptions.RequestException as e:
    print(f"Error making API request: {e}")
except ValueError as e:
    print(f"Error parsing response: {e}")`;
  }

  // File upload logic - handle multiple file types additively
  const chatInputNodeIds = getAllChatInputNodeIds(tweaks);
  const fileNodeIds = getAllFileNodeIds(tweaks);
  const nonFileTweaks = getNonFileTypeTweaks(tweaks);

  if (chatInputNodeIds.length === 0 && fileNodeIds.length === 0) {
    return getNewPythonApiCode({
      flowId,
      endpointName,
      processedPayload: { ...processedPayload, tweaks: nonFileTweaks },
      shouldDisplayApiKey,
    });
  }

  const authSection = shouldDisplayApiKey
    ? `api_key = 'YOUR_API_KEY_HERE'`
    : "";

  const headersSection = shouldDisplayApiKey
    ? `headers = {"x-api-key": api_key}`
    : "";

  // Build upload steps for each file component
  const uploadSteps: string[] = [];
  const tweakAssignments: string[] = [];

  // ChatInput files (v1 API)
  chatInputNodeIds.forEach((nodeId, index) => {
    uploadSteps.push(
      `# Step ${
        uploadSteps.length + 1
      }: Upload file for ChatInput ${nodeId}\nwith open(\"your_image_${
        index + 1
      }.jpg\", \"rb\") as f:\n    response = requests.post(\n        f\"{base_url}/api/v1/files/upload/{flow_id}\",\n        headers=headers,\n        files={\"file\": f}\n    )\n    response.raise_for_status()\n    chat_file_path_${
        index + 1
      } = response.json()[\"file_path\"]`,
    );

    const originalTweak = tweaks[nodeId];
    const modifiedTweak = { ...originalTweak };
    modifiedTweak.files = [`chat_file_path_${index + 1}`];
    tweakAssignments.push(
      `    \"${nodeId}\": ${JSON.stringify(modifiedTweak, null, 4)
        .split("\n")
        .join("\n    ")}`,
    );
  });

  // File/VideoFile components (v2 API)
  fileNodeIds.forEach((nodeId, index) => {
    uploadSteps.push(
      `# Step ${
        uploadSteps.length + 1
      }: Upload file for File/VideoFile ${nodeId}\nwith open(\"your_file_${
        index + 1
      }.pdf\", \"rb\") as f:\n    response = requests.post(\n        f\"{base_url}/api/v2/files\",\n        headers=headers,\n        files={\"file\": f}\n    )\n    response.raise_for_status()\n    file_path_${
        index + 1
      } = response.json()[\"path\"]`,
    );

    const originalTweak = tweaks[nodeId];
    const modifiedTweak = { ...originalTweak };
    if ("path" in originalTweak) {
      modifiedTweak.path = [`file_path_${index + 1}`];
    } else if ("file_path" in originalTweak) {
      modifiedTweak.file_path = `file_path_${index + 1}`;
    }
    tweakAssignments.push(
      `    \"${nodeId}\": ${JSON.stringify(modifiedTweak, null, 4)
        .split("\n")
        .join("\n    ")}`,
    );
  });

  // Add non-file tweaks
  Object.entries(nonFileTweaks).forEach(([nodeId, tweak]) => {
    tweakAssignments.push(
      `    \"${nodeId}\": ${JSON.stringify(tweak, null, 4)
        .split("\n")
        .join("\n    ")}`,
    );
  });

  const allTweaks =
    tweakAssignments.length > 0 ? tweakAssignments.join(",\n") : "";

  return `import requests
import os
import uuid

${authSection}base_url = "${baseUrl}"
flow_id = "${flowId}"

${headersSection}

${uploadSteps.join("\n\n")}

# Step ${uploadSteps.length + 1}: Execute flow with all file paths
payload = {
    "output_type": "${processedPayload.output_type || "chat"}",
    "input_type": "${processedPayload.input_type || "chat"}",
    "input_value": "${processedPayload.input_value || "Your message here"}",
    "session_id": str(uuid.uuid4()),
    "tweaks": {
${allTweaks}
    }
}

response = requests.post(
    f"{base_url}/api/v1/run/{endpointName or flowId}",
    headers={"Content-Type": "application/json", **headers},
    json=payload
)
response.raise_for_status()
print(response.json())`;
}
