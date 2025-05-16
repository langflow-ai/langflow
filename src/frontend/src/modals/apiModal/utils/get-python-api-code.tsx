import { customGetHostProtocol } from "@/customization/utils/custom-get-host-protocol";
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

  return `import argparse
import json
from argparse import RawTextHelpFormatter
import requests
from typing import Optional
import warnings
try:
    from langflow.load import upload_file
except ImportError:
    warnings.warn("Langflow provides a function to help you upload files to the flow. Please install langflow to use it.")
    upload_file = None

BASE_API_URL = "${window.location.protocol}//${window.location.host}"
FLOW_ID = "${flowId}"
ENDPOINT = "${endpointName || ""}" ${
    endpointName
      ? `# The endpoint name of the flow`
      : `# You can set a specific endpoint name in the flow settings`
  }

# You can tweak the flow by adding a tweaks dictionary
# e.g {"OpenAI-XXXXX": {"model_name": "gpt-4"}}
TWEAKS = ${tweaksString}

def run_flow(message: str,
  endpoint: str,
  output_type: str = "chat",
  input_type: str = "chat",
  tweaks: Optional[dict] = None,
  api_key: Optional[str] = None) -> dict:
    """
    Run a flow with a given message and optional tweaks.

    :param message: The message to send to the flow
    :param endpoint: The ID or the endpoint name of the flow
    :param tweaks: Optional tweaks to customize the flow
    :return: The JSON response from the flow
    """
    api_url = f"{BASE_API_URL}/api/v1/run/{endpoint}"

    payload = {
        ${!activeTweaks ? `"input_value": message,` : ""}
        "output_type": output_type,
        "input_type": input_type,
    }
    headers = None
    if tweaks:
        payload["tweaks"] = tweaks
    if api_key:
        headers = {"x-api-key": api_key}
    response = requests.post(api_url, json=payload, headers=headers)
    return response.json()

def main():
    parser = argparse.ArgumentParser(description="""Run a flow with a given message and optional tweaks.\nRun it like: python <your file>.py "your message here" --endpoint "your_endpoint" --tweaks '{"key": "value"}'""",
        formatter_class=RawTextHelpFormatter)
    parser.add_argument("message", type=str, help="The message to send to the flow")
    parser.add_argument("--endpoint", type=str, default=ENDPOINT or FLOW_ID, help="The ID or the endpoint name of the flow")
    parser.add_argument("--tweaks", type=str, help="JSON string representing the tweaks to customize the flow", default=json.dumps(TWEAKS))
    parser.add_argument("--api_key", type=str, help="API key for authentication", default=None)
    parser.add_argument("--output_type", type=str, default="chat", help="The output type")
    parser.add_argument("--input_type", type=str, default="chat", help="The input type")
    parser.add_argument("--upload_file", type=str, help="Path to the file to upload", default=None)
    parser.add_argument("--components", type=str, help="Components to upload the file to", default=None)

    args = parser.parse_args()
    try:
      tweaks = json.loads(args.tweaks)
    except json.JSONDecodeError:
      raise ValueError("Invalid tweaks JSON string")

    if args.upload_file:
        if not upload_file:
            raise ImportError("Langflow is not installed. Please install it to use the upload_file function.")
        elif not args.components:
            raise ValueError("You need to provide the components to upload the file to.")
        tweaks = upload_file(file_path=args.upload_file, host=BASE_API_URL, flow_id=args.endpoint, components=[args.components], tweaks=tweaks)

    response = run_flow(
        message=args.message,
        endpoint=args.endpoint,
        output_type=args.output_type,
        input_type=args.input_type,
        tweaks=tweaks,
        api_key=args.api_key
    )

    print(json.dumps(response, indent=2))

if __name__ == "__main__":
    main()
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
  endpointName,
}: {
  flowId: string;
  isAuthenticated: boolean;
  input_value: string;
  input_type: string;
  output_type: string;
  tweaksObject: any;
  activeTweaks: boolean;
  endpointName: string;
}): string {
  const { protocol, host } = customGetHostProtocol();
  const apiUrl = `${protocol}//${host}/api/v1/run/${endpointName || flowId}`;

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
