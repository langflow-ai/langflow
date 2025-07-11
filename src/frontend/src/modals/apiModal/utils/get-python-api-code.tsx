import { customGetHostProtocol } from "@/customization/utils/custom-get-host-protocol";
import { hasChatInputFiles, hasFileTweaks, getChatInputNodeId, getFileNodeId } from "./detect-file-tweaks";

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

  // File upload logic
  if (hasChatFiles) {
    // Chat Input files - use v1 upload API + run endpoint with tweaks
    const chatInputNodeId = getChatInputNodeId(tweaks) || "ChatInput-NodeId";
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

    return `import requests
import os

${authSection}base_url = "${baseUrl}"
flow_id = "${flowId}"

# Step 1: Upload file for Chat Input
${headersSection}

with open("your-image.jpg", "rb") as f:
    response = requests.post(
        f"{base_url}/api/v1/files/upload/{flow_id}",
        headers=headers,
        files={"file": f}
    )
    response.raise_for_status()
    file_path = response.json()["file_path"]

# Step 2: Execute flow
payload = {
    "output_type": "${processedPayload.output_type || "chat"}",
    "input_type": "${processedPayload.input_type || "chat"}",
    "input_value": "${processedPayload.input_value || "Your message here"}",
    "tweaks": {
        "${chatInputNodeId}": {
            "files": file_path
        }
    }
}

response = requests.post(
    f"{base_url}/api/v1/run/{flow_id}?stream=false",
    headers={"Content-Type": "application/json", **headers},
    json=payload
)
response.raise_for_status()
print(response.json())`;
  } else {
    // File/VideoFile components - use v2 upload API + run endpoint
    const fileNodeId = getFileNodeId(tweaks) || "File-NodeId";
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

    return `import requests
import os

${authSection}base_url = "${baseUrl}"
flow_id = "${flowId}"

# Step 1: Upload file
${headersSection}

with open("your-file.pdf", "rb") as f:
    response = requests.post(
        f"{base_url}/api/v2/files",
        headers=headers,
        files={"file": f}
    )
    response.raise_for_status()
    file_id = response.json()["id"]

# Step 2: Run flow with file_id
payload = {
    "output_type": "${processedPayload.output_type || "chat"}",
    "input_type": "${processedPayload.input_type || "chat"}",
    "input_value": "${processedPayload.input_value || "Your message here"}",
    "tweaks": {
        "${fileNodeId}": {
            "file_id": file_id
        }
    }
}

response = requests.post(
    f"{base_url}/api/v1/run/{flow_id}",
    headers={"Content-Type": "application/json", **headers},
    json=payload
)
response.raise_for_status()
print(response.json())`;
  }
}
