import { api } from "@/controllers/API/api";
import { useUtilityStore } from "@/stores/utilityStore";
import { customGetMCPUrl } from "../custom-mcp-url";

describe("customGetMCPUrl", () => {
  const originalBaseURL = api.defaults.baseURL;

  afterEach(() => {
    api.defaults.baseURL = originalBaseURL;
    useUtilityStore.setState({ mcpBaseUrl: "" });
  });

  it("uses mcpBaseUrl from store when set", () => {
    api.defaults.baseURL = "";
    useUtilityStore.setState({ mcpBaseUrl: "https://custom.example.com" });

    const url = customGetMCPUrl("proj-1");

    expect(url).toBe(
      "https://custom.example.com/api/v1/mcp/project/proj-1/streamable",
    );
  });

  it("mcpBaseUrl takes priority over api.defaults.baseURL", () => {
    api.defaults.baseURL = "https://api-default.example.com";
    useUtilityStore.setState({ mcpBaseUrl: "https://override.example.com" });

    const url = customGetMCPUrl("proj-1");

    expect(url).toBe(
      "https://override.example.com/api/v1/mcp/project/proj-1/streamable",
    );
  });

  it("falls back to api.defaults.baseURL when mcpBaseUrl is empty", () => {
    api.defaults.baseURL = "https://api-default.example.com";
    useUtilityStore.setState({ mcpBaseUrl: "" });

    const url = customGetMCPUrl("proj-1");

    expect(url).toBe(
      "https://api-default.example.com/api/v1/mcp/project/proj-1/streamable",
    );
  });

  it("falls back to window.location.origin when both are empty", () => {
    api.defaults.baseURL = "";
    useUtilityStore.setState({ mcpBaseUrl: "" });

    const url = customGetMCPUrl("proj-1");

    expect(url).toBe(
      `${window.location.origin}/api/v1/mcp/project/proj-1/streamable`,
    );
  });

  it("strips trailing slashes from mcpBaseUrl", () => {
    useUtilityStore.setState({ mcpBaseUrl: "https://example.com/" });

    const url = customGetMCPUrl("proj-1");

    expect(url).toBe(
      "https://example.com/api/v1/mcp/project/proj-1/streamable",
    );
  });

  it("strips multiple trailing slashes", () => {
    useUtilityStore.setState({ mcpBaseUrl: "https://example.com///" });

    const url = customGetMCPUrl("proj-1");

    expect(url).toBe(
      "https://example.com/api/v1/mcp/project/proj-1/streamable",
    );
  });

  it("returns SSE URL when transport is sse", () => {
    useUtilityStore.setState({ mcpBaseUrl: "https://example.com" });

    const url = customGetMCPUrl("proj-1", {}, "sse");

    expect(url).toBe("https://example.com/api/v1/mcp/project/proj-1/sse");
  });

  it("returns composer URL when useComposer is true and streamableHttpUrl is set", () => {
    useUtilityStore.setState({ mcpBaseUrl: "https://should-not-use.com" });

    const url = customGetMCPUrl(
      "proj-1",
      {
        useComposer: true,
        streamableHttpUrl: "https://composer.example.com/streamable",
      },
      "streamablehttp",
    );

    expect(url).toBe("https://composer.example.com/streamable");
  });
});
