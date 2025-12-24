import { customGetHostProtocol } from "./custom-get-host-protocol";

export function getApiSampleHeaders(
  language: "python" | "javascript" | "curl" | "json",
  includeWrapper: boolean = true,
): string {
  return "";
}

export function formatJsHeadersForInline(): string {
  const headers = getApiSampleHeaders("javascript", false);
  if (!headers) return "";
  // Format with proper indentation, add leading newline and trailing comma
  return (
    "\n" +
    headers
      .split("\n")
      .map((line) => `                ${line}`)
      .join("\n") +
    ","
  );
}

export function getWidgetAdditionalHeaders(): string {
  return "";
}

export function getBaseUrl(): string {
  const { protocol, host } = customGetHostProtocol();

  return `${protocol}//${host}`;
}
