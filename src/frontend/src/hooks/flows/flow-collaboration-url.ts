import { BASE_URL_API } from "@/customization/config-constants";

/** Build the collaborative editing WebSocket URL for a flow. */
export function buildFlowCollaborationWebSocketUrl(flowId: string): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const basePath = BASE_URL_API.startsWith("/")
    ? BASE_URL_API
    : `/${BASE_URL_API}`;
  const normalizedBase = basePath.endsWith("/") ? basePath : `${basePath}/`;
  return `${protocol}//${window.location.host}${normalizedBase}flows/${flowId}/collab`;
}
