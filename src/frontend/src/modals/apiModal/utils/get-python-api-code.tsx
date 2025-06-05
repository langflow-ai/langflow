import { customGetHostProtocol } from "@/customization/utils/custom-get-host-protocol";

export function getNewPythonApiCode({
  flowId,
  isAuthenticated,
  endpointName,
  processedPayload,
}: {
  flowId: string;
  isAuthenticated: boolean;
  endpointName: string;
  processedPayload: any;
}): string {
  const { protocol, host } = customGetHostProtocol();
  const apiUrl = `${protocol}//${host}/api/v1/run/${endpointName || flowId}`;

  const payloadString = JSON.stringify(processedPayload, null, 4)
    .replace(/true/g, "True")
    .replace(/false/g, "False")
    .replace(/null/g, "None");

  return `import requests
${
  isAuthenticated
    ? `import os

# API Configuration
try:
    api_key = os.environ["LANGFLOW_API_KEY"]
except KeyError:
    raise ValueError("LANGFLOW_API_KEY environment variable not found. Please set your API key in the environment variables.")
`
    : ""
}
url = "${apiUrl}"  # The complete API endpoint URL for this flow

# Request payload configuration
payload = ${payloadString}

# Request headers
headers = {
    "Content-Type": "application/json"${isAuthenticated ? ',\n    "x-api-key": api_key  # Authentication key from environment variable' : ""}
}

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
