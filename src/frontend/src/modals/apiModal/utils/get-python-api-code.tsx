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
