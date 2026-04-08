/**
 * Tests for MCP OAuth utility functions.
 *
 * Covers: extractOAuthError, initiateMCPOAuth, checkMCPOAuthStatus,
 * and handleMCPOAuthFlow (popup + polling logic).
 */

const mockApiPost = jest.fn();
const mockApiGet = jest.fn();

jest.mock("@/controllers/API/api", () => ({
  api: {
    post: mockApiPost,
    get: mockApiGet,
  },
}));

import {
  checkMCPOAuthStatus,
  extractOAuthError,
  handleMCPOAuthFlow,
  initiateMCPOAuth,
  type MCPOAuthError,
  type MCPOAuthInitiateResponse,
  type MCPOAuthStatusResponse,
} from "../use-mcp-oauth";

// ---------------------------------------------------------------------------
// extractOAuthError
// ---------------------------------------------------------------------------

describe("extractOAuthError", () => {
  it("returns null when error is undefined", () => {
    expect(extractOAuthError(undefined)).toBeNull();
  });

  it("returns null when error has no response", () => {
    expect(extractOAuthError(new Error("network error"))).toBeNull();
  });

  it("returns null when detail is a plain string", () => {
    const err = { response: { data: { detail: "Unauthorized" } } };
    expect(extractOAuthError(err)).toBeNull();
  });

  it("returns null when detail.error is not 'oauth_required'", () => {
    const err = {
      response: {
        data: {
          detail: {
            error: "forbidden",
            message: "Not allowed",
            server_url: "https://mcp.example.com",
            initiate_endpoint: "/api/v1/mcp/oauth/initiate",
          },
        },
      },
    };
    expect(extractOAuthError(err)).toBeNull();
  });

  it("returns the OAuth error when detail.error is 'oauth_required'", () => {
    const oauthError: MCPOAuthError = {
      error: "oauth_required",
      message: "Authentication required",
      server_url: "https://mcp.example.com",
      initiate_endpoint: "/api/v1/mcp/oauth/initiate",
    };
    const err = { response: { data: { detail: oauthError } } };

    const result = extractOAuthError(err);

    expect(result).not.toBeNull();
    expect(result!.error).toBe("oauth_required");
    expect(result!.server_url).toBe("https://mcp.example.com");
  });

  it("includes optional fields when present", () => {
    const oauthError: MCPOAuthError = {
      error: "oauth_required",
      message: "Auth needed",
      server_url: "https://mcp.example.com",
      initiate_endpoint: "/api/v1/mcp/oauth/initiate",
      client_id: "my-client",
      scopes: ["read", "write"],
    };
    const err = { response: { data: { detail: oauthError } } };

    const result = extractOAuthError(err);

    expect(result!.client_id).toBe("my-client");
    expect(result!.scopes).toEqual(["read", "write"]);
  });
});

// ---------------------------------------------------------------------------
// initiateMCPOAuth
// ---------------------------------------------------------------------------

describe("initiateMCPOAuth", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("posts to the correct endpoint with server_url", async () => {
    const mockResponse: MCPOAuthInitiateResponse = {
      flow_id: "flow-123",
      auth_url: "https://auth.example.com/go",
      expires_in: 600,
    };
    mockApiPost.mockResolvedValue({ data: mockResponse });

    const result = await initiateMCPOAuth("https://mcp.example.com");

    expect(mockApiPost).toHaveBeenCalledWith(
      "/api/v1/mcp/oauth/initiate",
      expect.objectContaining({ server_url: "https://mcp.example.com" }),
    );
    expect(result.flow_id).toBe("flow-123");
    expect(result.auth_url).toBe("https://auth.example.com/go");
  });

  it("includes optional fields when provided", async () => {
    mockApiPost.mockResolvedValue({
      data: {
        flow_id: "f",
        auth_url: "https://auth.example.com/go",
        expires_in: 600,
      },
    });

    await initiateMCPOAuth("https://mcp.example.com", {
      clientId: "my-client",
      clientSecret: "s3cr3t",
      scopes: ["openid"],
    });

    expect(mockApiPost).toHaveBeenCalledWith(
      "/api/v1/mcp/oauth/initiate",
      expect.objectContaining({
        client_id: "my-client",
        client_secret: "s3cr3t",
        scopes: ["openid"],
      }),
    );
  });

  it("propagates API errors", async () => {
    mockApiPost.mockRejectedValue(new Error("Network error"));
    await expect(initiateMCPOAuth("https://mcp.example.com")).rejects.toThrow(
      "Network error",
    );
  });
});

// ---------------------------------------------------------------------------
// checkMCPOAuthStatus
// ---------------------------------------------------------------------------

describe("checkMCPOAuthStatus", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("gets status from the correct endpoint", async () => {
    const mockStatus: MCPOAuthStatusResponse = { status: "pending" };
    mockApiGet.mockResolvedValue({ data: mockStatus });

    const result = await checkMCPOAuthStatus("flow-123");

    expect(mockApiGet).toHaveBeenCalledWith(
      "/api/v1/mcp/oauth/status/flow-123",
    );
    expect(result.status).toBe("pending");
  });

  it("returns complete status when flow is done", async () => {
    mockApiGet.mockResolvedValue({ data: { status: "complete" } });
    const result = await checkMCPOAuthStatus("flow-abc");
    expect(result.status).toBe("complete");
  });
});

// ---------------------------------------------------------------------------
// handleMCPOAuthFlow
// ---------------------------------------------------------------------------

describe("handleMCPOAuthFlow", () => {
  const SERVER_URL = "https://mcp.example.com";

  let mockPopup: { closed: boolean; close: jest.Mock };

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();

    mockPopup = { closed: false, close: jest.fn() };
    Object.defineProperty(window, "open", {
      writable: true,
      value: jest.fn(() => mockPopup),
    });
    // jsdom marks window.location non-configurable; delete first to allow redefine
    delete (window as any).location;
    (window as any).location = { origin: "https://app.example.com" };
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("returns success when OAuth flow completes", async () => {
    mockApiPost.mockResolvedValue({
      data: {
        flow_id: "flow-123",
        auth_url: "https://auth.example.com/go",
        expires_in: 600,
      },
    });
    mockApiGet.mockResolvedValue({ data: { status: "complete" } });

    const promise = handleMCPOAuthFlow(SERVER_URL);
    await jest.runAllTimersAsync();
    const result = await promise;

    expect(result.success).toBe(true);
  });

  it("returns failure when OAuth flow errors", async () => {
    mockApiPost.mockResolvedValue({
      data: {
        flow_id: "flow-123",
        auth_url: "https://auth.example.com/go",
        expires_in: 600,
      },
    });
    mockApiGet.mockResolvedValue({
      data: { status: "error", error_message: "provider rejected" },
    });

    const promise = handleMCPOAuthFlow(SERVER_URL);
    await jest.runAllTimersAsync();
    const result = await promise;

    expect(result.success).toBe(false);
    expect(result.error).toContain("provider rejected");
  });

  it("returns failure when popup cannot be opened", async () => {
    mockApiPost.mockResolvedValue({
      data: {
        flow_id: "flow-123",
        auth_url: "https://auth.example.com/go",
        expires_in: 600,
      },
    });
    (window.open as jest.Mock).mockReturnValue(null); // popup blocked

    const promise = handleMCPOAuthFlow(SERVER_URL);
    await jest.runAllTimersAsync();
    const result = await promise;

    expect(result.success).toBe(false);
    expect(result.error).toMatch(/popup/i);
  });

  it("accepts MCPOAuthError object and extracts server_url", async () => {
    const oauthError: MCPOAuthError = {
      error: "oauth_required",
      message: "Auth needed",
      server_url: SERVER_URL,
      initiate_endpoint: "/api/v1/mcp/oauth/initiate",
      client_id: "my-client",
    };
    mockApiPost.mockResolvedValue({
      data: {
        flow_id: "flow-123",
        auth_url: "https://auth.example.com/go",
        expires_in: 600,
      },
    });
    mockApiGet.mockResolvedValue({ data: { status: "complete" } });

    const promise = handleMCPOAuthFlow(oauthError);
    await jest.runAllTimersAsync();
    const result = await promise;

    expect(mockApiPost).toHaveBeenCalledWith(
      "/api/v1/mcp/oauth/initiate",
      expect.objectContaining({
        server_url: SERVER_URL,
        client_id: "my-client",
      }),
    );
    expect(result.success).toBe(true);
  });

  it("calls onStatusChange callback with each polled status", async () => {
    mockApiPost.mockResolvedValue({
      data: {
        flow_id: "flow-123",
        auth_url: "https://auth.example.com/go",
        expires_in: 600,
      },
    });
    mockApiGet
      .mockResolvedValueOnce({ data: { status: "pending" } })
      .mockResolvedValue({ data: { status: "complete" } });

    const onStatusChange = jest.fn();
    const promise = handleMCPOAuthFlow(SERVER_URL, { onStatusChange });
    await jest.runAllTimersAsync();
    await promise;

    expect(onStatusChange).toHaveBeenCalledWith(
      expect.objectContaining({ status: "pending" }),
    );
    expect(onStatusChange).toHaveBeenCalledWith(
      expect.objectContaining({ status: "complete" }),
    );
  });

  it("closes the popup when the flow completes", async () => {
    mockApiPost.mockResolvedValue({
      data: {
        flow_id: "flow-123",
        auth_url: "https://auth.example.com/go",
        expires_in: 600,
      },
    });
    mockApiGet.mockResolvedValue({ data: { status: "complete" } });

    const promise = handleMCPOAuthFlow(SERVER_URL);
    await jest.runAllTimersAsync();
    await promise;

    expect(mockPopup.close).toHaveBeenCalled();
  });

  it("returns failure when initiate API call throws", async () => {
    mockApiPost.mockRejectedValue({ message: "Network error" });

    const promise = handleMCPOAuthFlow(SERVER_URL);
    await jest.runAllTimersAsync();
    const result = await promise;

    expect(result.success).toBe(false);
    expect(result.error).toBeDefined();
  });
});
