import { ENABLE_DATASTAX_LANGFLOW } from "@/customization/feature-flags";
import { customGetHostProtocol } from "@/customization/utils/custom-get-host-protocol";
import { GetCodeType } from "@/types/tweaks";

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
}): string {
  const { protocol, host } = customGetHostProtocol();
  const apiUrl = `${protocol}//${host}/api/v1/run/${endpointName || flowId}`;

  // Auto-detect if no platform specified
  const detectedPlatform =
    platform ||
    (/Windows|Win32|Win64|WOW32|WOW64/i.test(navigator.userAgent)
      ? "powershell"
      : "unix");

  const singleLinePayload = JSON.stringify(processedPayload);

  if (detectedPlatform === "powershell") {
    // PowerShell with here-string (most robust for complex JSON)
    return `if (-not $env:LANGFLOW_API_KEY) {
    Write-Error "LANGFLOW_API_KEY environment variable not found"
    exit 1
}

$jsonData = @'
${singleLinePayload}
'@

curl --request POST \`
     --url "${apiUrl}?stream=false" \`
     --header "Content-Type: application/json" \`
     --header "x-api-key: $env:LANGFLOW_API_KEY" \`
     --data $jsonData`;
  } else {
    // Unix-like systems (Linux, Mac, WSL2)
    const unixFormattedPayload = JSON.stringify(processedPayload, null, 2)
      .split("\n")
      .map((line, index) => (index === 0 ? line : "         " + line))
      .join("\n\t\t");

    return `# Get API key from environment variable
if [ -z "$LANGFLOW_API_KEY" ]; then
    echo "Error: LANGFLOW_API_KEY environment variable not found. Please set your API key in the environment variables."
    exit 1
fi

curl --request POST \\
     --url '${apiUrl}?stream=false' \\
     --header 'Content-Type: application/json' \\
     --header "x-api-key: $LANGFLOW_API_KEY" \\
     --data '${unixFormattedPayload}'`;
  }
}
