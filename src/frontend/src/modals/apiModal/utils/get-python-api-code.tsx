import { customGetHostProtocol } from "@/customization/utils/custom-get-host-protocol";
import { hasChatInputFiles, hasFileTweaks, getChatInputNodeId, getFileNodeId, getAllChatInputNodeIds, getAllFileNodeIds, getNonFileTypeTweaks } from "./detect-file-tweaks";

export function getNewPythonApiCode({
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
    const payloadString = JSON.stringify(processedPayload, null, 4)
      .replace(/true/g, "True")
      .replace(/false/g, "False")
      .replace(/null/g, "None");

    const authSection = isAuth
      ? `# API Configuration
try:
    api_key = os.environ["LANGFLOW_API_KEY"]
except KeyError:
    raise ValueError("LANGFLOW_API_KEY environment variable not found. Please set your API key in the environment variables.")

`
      : "";

    const headersSection = isAuth
      ? `# Request headers
headers = {
    "Content-Type": "application/json",
    "x-api-key": api_key  # Authentication key from environment variable
}`
      : `# Request headers
headers = {
    "Content-Type": "application/json"
}`;

    return `import requests
import os

${authSection}url = "${apiUrl}"  # The complete API endpoint URL for this flow

# Request payload configuration
payload = ${payloadString}

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

  const authSection = isAuth
    ? `# API Configuration
try:
    api_key = os.environ["LANGFLOW_API_KEY"]
except KeyError:
    raise ValueError("LANGFLOW_API_KEY environment variable not found. Please set your API key in the environment variables.")

`
    : "";

  const headersSection = isAuth
    ? `headers = {"x-api-key": api_key} if api_key else {}`
    : `headers = {}`;

  // Build upload steps for each file component
  const uploadSteps: string[] = [];
  const tweakAssignments: string[] = [];

  // ChatInput files (v1 API)
  chatInputNodeIds.forEach((nodeId, index) => {
    uploadSteps.push(`# Step ${uploadSteps.length + 1}: Upload file for ChatInput ${nodeId}
with open("your_image_${index + 1}.jpg", "rb") as f:
    response = requests.post(
        f"{base_url}/api/v1/files/upload/{flow_id}",
        headers=headers,
        files={"file": f}
    )
    response.raise_for_status()
    chat_file_path_${index + 1} = response.json()["file_path"]`);
    
    tweakAssignments.push(`    "${nodeId}": {
        "files": chat_file_path_${index + 1}
    }`);
  });

  // File/VideoFile components (v2 API)
  fileNodeIds.forEach((nodeId, index) => {
    uploadSteps.push(`# Step ${uploadSteps.length + 1}: Upload file for File/VideoFile ${nodeId}
with open("your_file_${index + 1}.pdf", "rb") as f:
    response = requests.post(
        f"{base_url}/api/v2/files",
        headers=headers,
        files={"file": f}
    )
    response.raise_for_status()
    file_path_${index + 1} = response.json()["path"]`);
    
    tweakAssignments.push(`    "${nodeId}": {
        "path": [file_path_${index + 1}]
    }`);
  });

  // Add non-file tweaks
  Object.entries(nonFileTweaks).forEach(([nodeId, tweak]) => {
    tweakAssignments.push(`    "${nodeId}": ${JSON.stringify(tweak, null, 4).split('\n').join('\n    ')}`);
  });

  const allTweaks = tweakAssignments.length > 0 ? tweakAssignments.join(',\n') : '';

  return `import requests
import os

${authSection}base_url = "${baseUrl}"
flow_id = "${flowId}"

${headersSection}

${uploadSteps.join('\n\n')}

# Step ${uploadSteps.length + 1}: Execute flow with all file paths
payload = {
    "output_type": "${processedPayload.output_type || "chat"}",
    "input_type": "${processedPayload.input_type || "chat"}",
    "input_value": "${processedPayload.input_value || "Your message here"}",
    "tweaks": {
${allTweaks}
    }
}

response = requests.post(
    f"{base_url}/api/v1/run/{endpointName || flowId}",
    headers={"Content-Type": "application/json", **headers},
    json=payload
)
response.raise_for_status()
print(response.json())`;
}
