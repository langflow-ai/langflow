import { GetCodeType } from "@/types/tweaks";

/**
 * Function to get the python code for the API
 * @param {string} flowId - The id of the flow
 * @param {boolean} isAuth - If the API is authenticated
 * @param {any[]} tweaksBuildedObject - The tweaks
 * @param {string} [endpointName] - The optional endpoint name
 * @returns {string} - The python code
 */
export default function getPythonApiCode({
  flowId,
  tweaksBuildedObject,
  endpointName,
  activeTweaks,
}: GetCodeType): string {
  let tweaksString = "{}";
  if (tweaksBuildedObject)
    tweaksString = JSON.stringify(tweaksBuildedObject, null, 2)
      .replace(/true/g, "True")
      .replace(/false/g, "False")
      .replace(/null|undefined/g, "None");

  return `import requests

# API Configuration
BASE_API_URL = "${window.location.protocol}//${window.location.host}"
FLOW_ID = "${flowId}"  # Flow ID from Langflow
ENDPOINT = "${endpointName || ""}"  # Optional: Use a specific endpoint name if defined in the flow settings

# Flow customization
# You can tweak the flow by adding a tweaks dictionary
# e.g {"OpenAI-XXXXX": {"model_name": "gpt-4"}}
TWEAKS = ${tweaksString}

# Session configuration
message = "Hello, world!"
session_id = "user_1"

# Construct API URL
api_url = f"{BASE_API_URL}/api/v1/run/{ENDPOINT or FLOW_ID}"

# Prepare request payload
payload = {
    ${
      !activeTweaks
        ? `"input_value": message,
    `
        : ""
    }"session_id": session_id,  # Optional: Use session tracking if needed
    "tweaks": TWEAKS  # Optional: Add tweaks to customize the flow
}

try:
    # Send API request
    response = requests.post(api_url, json=payload)
    response.raise_for_status()  # Raise exception for bad status codes

    # Process response
    result = response.json()
    print(result)

except requests.exceptions.RequestException as e:
    print(f"Error making API request: {e}")
except ValueError as e:
    print(f"Error parsing JSON response: {e}")
`;
}

export function getNewPythonApiCode({
  flowId,
  isAuthenticated,
  input_value,
  input_type,
  output_type,
  tweaksObject,
  activeTweaks,
}: {
  flowId: string;
  isAuthenticated: boolean;
  input_value: string;
  input_type: string;
  output_type: string;
  tweaksObject: any;
  activeTweaks: boolean;
}): string {
  const host = window.location.host;
  const protocol = window.location.protocol;
  const apiUrl = `${protocol}//${host}/api/v1/run/${flowId}`;

  const tweaksString =
    tweaksObject && activeTweaks
      ? JSON.stringify(tweaksObject, null, 4)
          .replace(/true/g, "True")
          .replace(/false/g, "False")
          .replace(/null/g, "None")
      : "{}";

  return `import requests
${
  isAuthenticated
    ? `import os
# API Configuration
try:
    api_key = os.environ["LANGFLOW_API_KEY"]
except KeyError:
    raise ValueError("LANGFLOW_API_KEY environment variable not found. Please set your API key in the environment variables.")\n`
    : ""
}url = "${apiUrl}"  # The complete API endpoint URL for this flow

# Request payload configuration
payload = {
    "input_value": "${input_value}",  # The input value to be processed by the flow
    "output_type": "${output_type}",  # Specifies the expected output format
    "input_type": "${input_type}"  # Specifies the input format${
      activeTweaks && tweaksObject
        ? `,
    "tweaks": ${tweaksString}  # Custom tweaks to modify flow behavior`
        : ""
    }
}

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
    print(f"Error parsing response: {e}")
    `;
}
