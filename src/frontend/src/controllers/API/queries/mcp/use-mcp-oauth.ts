import { api } from "../../api";

// Types for MCP OAuth
export interface MCPOAuthInitiateResponse {
  flow_id: string;
  auth_url: string;
  expires_in: number;
}

export interface MCPOAuthStatusResponse {
  status: "pending" | "complete" | "error" | "expired";
  error_message?: string;
  server_url?: string;
}

export interface MCPOAuthError {
  error: "oauth_required";
  message: string;
  server_url: string;
  initiate_endpoint: string;
  client_id?: string;
  client_secret?: string;
  redirect_uri?: string;
  scopes?: string[];
}

/**
 * Extract OAuth error details from an error response
 */
export function extractOAuthError(error: any): MCPOAuthError | null {
  const detail = error?.response?.data?.detail;
  if (
    typeof detail === "object" &&
    detail !== null &&
    detail.error === "oauth_required"
  ) {
    return detail as MCPOAuthError;
  }
  return null;
}

/**
 * Initiate an OAuth flow for an MCP server
 */
export async function initiateMCPOAuth(
  serverUrl: string,
  options?: {
    clientId?: string;
    clientSecret?: string;
    redirectUri?: string;
    scopes?: string[];
  }
): Promise<MCPOAuthInitiateResponse> {
  const response = await api.post<MCPOAuthInitiateResponse>(
    "/api/v1/mcp/oauth/initiate",
    {
      server_url: serverUrl,
      callback_base_url: window.location.origin,
      client_id: options?.clientId,
      client_secret: options?.clientSecret,
      redirect_uri: options?.redirectUri,
      scopes: options?.scopes,
    }
  );
  return response.data;
}

/**
 * Check the status of an OAuth flow
 */
export async function checkMCPOAuthStatus(
  flowId: string
): Promise<MCPOAuthStatusResponse> {
  const response = await api.get<MCPOAuthStatusResponse>(
    `/api/v1/mcp/oauth/status/${flowId}`
  );
  return response.data;
}

/**
 * Poll for OAuth flow completion
 */
async function pollOAuthStatus(
  flowId: string,
  onStatusChange?: (status: MCPOAuthStatusResponse) => void,
  maxAttempts: number = 300, // 10 minutes at 2 second intervals
  intervalMs: number = 2000
): Promise<MCPOAuthStatusResponse> {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const status = await checkMCPOAuthStatus(flowId);
    onStatusChange?.(status);

    if (status.status !== "pending") {
      return status;
    }

    // Wait before next poll
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  return { status: "expired", error_message: "OAuth flow timed out" };
}

/**
 * Open OAuth popup and handle the flow
 * Can be called with just serverUrl, or with full OAuth error details
 */
export async function handleMCPOAuthFlow(
  serverUrlOrError: string | MCPOAuthError,
  options?: {
    clientId?: string;
    clientSecret?: string;
    redirectUri?: string;
    scopes?: string[];
    onStatusChange?: (status: MCPOAuthStatusResponse) => void;
  }
): Promise<{ success: boolean; error?: string }> {
  // Extract parameters from error object if provided
  const serverUrl = typeof serverUrlOrError === "string"
    ? serverUrlOrError
    : serverUrlOrError.server_url;

  const clientId = options?.clientId ??
    (typeof serverUrlOrError === "object" ? serverUrlOrError.client_id : undefined);
  const clientSecret = options?.clientSecret ??
    (typeof serverUrlOrError === "object" ? serverUrlOrError.client_secret : undefined);
  const redirectUri = options?.redirectUri ??
    (typeof serverUrlOrError === "object" ? serverUrlOrError.redirect_uri : undefined);
  const scopes = options?.scopes ??
    (typeof serverUrlOrError === "object" ? serverUrlOrError.scopes : undefined);
  try {
    // Initiate the OAuth flow with extracted credentials
    const { flow_id, auth_url } = await initiateMCPOAuth(serverUrl, {
      clientId,
      clientSecret,
      redirectUri,
      scopes,
    });

    // Open the OAuth popup
    const popup = window.open(
      auth_url,
      "mcp_oauth_popup",
      "width=600,height=700,menubar=no,toolbar=no,location=no,status=no"
    );

    if (!popup) {
      return {
        success: false,
        error: "Failed to open OAuth popup. Please allow popups for this site.",
      };
    }

    // Poll for completion
    const finalStatus = await pollOAuthStatus(flow_id, (status) => {
      options?.onStatusChange?.(status);

      // Close popup if flow is complete
      if (status.status !== "pending" && popup && !popup.closed) {
        popup.close();
      }
    });

    // Ensure popup is closed
    if (popup && !popup.closed) {
      popup.close();
    }

    return finalStatus.status === "complete"
      ? { success: true }
      : { success: false, error: finalStatus.error_message || `OAuth flow ${finalStatus.status}` };
  } catch (error: any) {
    const message =
      error?.response?.data?.detail ||
      error?.message ||
      "OAuth authentication failed";
    return { success: false, error: message };
  }
}
