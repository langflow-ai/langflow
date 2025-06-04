import { customGetHostProtocol } from "@/customization/utils/custom-get-host-protocol";
import { buildBasePayload, getFormattedTweaksString } from "./payload-utils";

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

  // Use improved payload building logic that considers node types
  const basePayload = buildBasePayload(
    tweaksObject,
    activeTweaks,
    input_value,
    input_type,
    output_type,
  );
  const tweaksString = getFormattedTweaksString(
    tweaksObject,
    activeTweaks,
    "python",
    4,
  );

  // Generate payload entries with proper Python formatting
  const payloadEntries = Object.entries(basePayload).map(([key, value]) => {
    const comment =
      key === "input_value"
        ? "  # The input value to be processed by the flow"
        : key === "output_type"
          ? "  # Specifies the expected output format"
          : key === "input_type"
            ? "  # Specifies the input format"
            : "";
    return `    "${key}": "${value}"${comment}`;
  });

  const hasPayloadEntries = payloadEntries.length > 0;
  const hasTweaks = activeTweaks && tweaksObject;

  // Build payload string with proper comma placement
  const payloadString = hasPayloadEntries
    ? payloadEntries
        .map((entry, index) => {
          const isLastPayloadEntry = index === payloadEntries.length - 1;
          const needsComma = hasTweaks || !isLastPayloadEntry;
          if (needsComma) {
            const commentIndex = entry.indexOf("  #");
            if (commentIndex !== -1) {
              return (
                entry.slice(0, commentIndex) + "," + entry.slice(commentIndex)
              );
            } else {
              return entry + ",";
            }
          }
          return entry;
        })
        .join("\n")
    : "";

  const tweaksLine = hasTweaks
    ? `${hasPayloadEntries ? "\n" : ""}    "tweaks": ${tweaksString} # Custom tweaks to modify flow behavior`
    : "";

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
