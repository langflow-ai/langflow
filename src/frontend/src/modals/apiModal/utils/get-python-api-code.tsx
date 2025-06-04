import { customGetHostProtocol } from "@/customization/utils/custom-get-host-protocol";
import {
  buildBasePayload,
  buildPayloadString,
  generatePayloadEntries,
  generateTweaksLine,
  getFormattedTweaksString,
} from "./payload-utils";

export function getNewPythonApiCode({
  flowId,
  isAuthenticated,
  input_value,
  input_type,
  output_type,
  tweaksObject,
  activeTweaks,
  endpointName,
  excludedFields,
}: {
  flowId: string;
  isAuthenticated: boolean;
  input_value: string;
  input_type: string;
  output_type: string;
  tweaksObject: any;
  activeTweaks: boolean;
  endpointName: string;
  excludedFields?: Set<string>;
}): string {
  const { protocol, host } = customGetHostProtocol();
  const apiUrl = `${protocol}//${host}/api/v1/run/${endpointName || flowId}`;

  // Use improved payload building logic that considers node types
  const basePayload = buildBasePayload(
    tweaksObject,
    activeTweaks,
    input_value,
    input_type,
    output_type,
    false, // Don't include session_id for Python by default
    excludedFields,
  );

  const tweaksString = getFormattedTweaksString(
    tweaksObject,
    activeTweaks,
    "python",
    4,
  );

  // Generate payload using utility functions
  const payloadEntries = generatePayloadEntries(basePayload, "python");
  const hasTweaks = activeTweaks && tweaksObject;
  const hasPayloadEntries = payloadEntries.length > 0;

  const payloadString = buildPayloadString(payloadEntries, hasTweaks, "python");
  const tweaksLine = generateTweaksLine(
    hasTweaks,
    hasPayloadEntries,
    tweaksString,
    "python",
  );

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
}url = "${apiUrl}"  # The complete API endpoint URL for this flow

# Request payload configuration
payload = {
${payloadString}${tweaksLine}
}

# Request headers
headers = {
    "Content-Type": "application/json"${
      isAuthenticated
        ? `,
    "x-api-key": api_key  # Authentication key from environment variable`
        : ""
    }
}

try:
    # Send API request
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()  # Raise exception for bad status codes

    # Print response
    print(response.text)

except requests.exceptions.RequestException as e:
    print(f"Error making API request: {e}")
except ValueError as e:
    print(f"Error parsing response: {e}")
`;
}
