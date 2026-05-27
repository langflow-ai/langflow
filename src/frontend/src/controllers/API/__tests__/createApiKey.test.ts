import { createApiKey } from "../index";

const mockPost = jest.fn();

jest.mock("../api", () => ({
  api: { post: (...args: unknown[]) => mockPost(...args) },
}));

jest.mock("@/customization/utils/urls", () => ({
  getBaseUrl: () => "/api/v1/",
}));

describe("createApiKey", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("posts to the api_key endpoint with just the name when no expiry is given", async () => {
    mockPost.mockResolvedValue({ status: 200, data: { api_key: "sk-abc" } }); // pragma: allowlist secret
    await createApiKey("my-key");
    expect(mockPost).toHaveBeenCalledWith("/api/v1/api_key/", {
      name: "my-key",
    });
  });

  it("includes expires_at in the payload when a non-null value is provided", async () => {
    mockPost.mockResolvedValue({ status: 200, data: { api_key: "sk-abc" } }); // pragma: allowlist secret
    const expiry = "2025-12-31T00:00:00.000Z";
    await createApiKey("expiring-key", expiry);
    expect(mockPost).toHaveBeenCalledWith("/api/v1/api_key/", {
      name: "expiring-key",
      expires_at: expiry,
    });
  });

  it("does NOT include expires_at when null is passed", async () => {
    mockPost.mockResolvedValue({ status: 200, data: { api_key: "sk-abc" } }); // pragma: allowlist secret
    await createApiKey("no-expiry-key", null);
    expect(mockPost).toHaveBeenCalledWith("/api/v1/api_key/", {
      name: "no-expiry-key",
    });
  });

  it("returns the response data on HTTP 200", async () => {
    const data = { api_key: "sk-returned", id: "abc-123" }; // pragma: allowlist secret
    mockPost.mockResolvedValue({ status: 200, data });
    const result = await createApiKey("my-key");
    expect(result).toEqual(data);
  });

  it("re-throws when the API call rejects", async () => {
    mockPost.mockRejectedValue(new Error("Network error"));
    await expect(createApiKey("my-key")).rejects.toThrow("Network error");
  });
});
