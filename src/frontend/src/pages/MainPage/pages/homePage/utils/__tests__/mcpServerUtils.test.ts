import {
  buildMcpServerJson,
  createSyntaxHighlighterStyle,
  extractInstalledClientNames,
  getAuthHeaders,
  getCommandForPlatform,
  getServerName,
  mapFlowsToTools,
} from "../mcpServerUtils";

describe("mcpServerUtils", () => {
  describe("getCommandForPlatform", () => {
    it("returns cmd for windows platform", () => {
      expect(getCommandForPlatform("windows")).toBe("cmd");
    });

    it("returns wsl for wsl platform", () => {
      expect(getCommandForPlatform("wsl")).toBe("wsl");
    });

    it("returns uvx for macoslinux platform", () => {
      expect(getCommandForPlatform("macoslinux")).toBe("uvx");
    });

    it("returns uvx for undefined platform", () => {
      expect(getCommandForPlatform()).toBe("uvx");
    });
  });

  describe("getServerName", () => {
    it("generates server name with lf- prefix", () => {
      const name = getServerName("My Project");
      expect(name).toBe("lf-my_project");
    });

    it("converts to snake_case and lowercase", () => {
      const name = getServerName("Test Project Name");
      expect(name).toBe("lf-test_project_name");
    });

    it("truncates long names", () => {
      const longName = "a".repeat(100);
      const name = getServerName(longName, 20);
      expect(name.length).toBeLessThanOrEqual(20);
      expect(name).toMatch(/^lf-/);
    });

    it("handles undefined folderName", () => {
      const name = getServerName();
      expect(name).toBe("lf-project");
    });
  });

  describe("getAuthHeaders", () => {
    it("returns empty string for auto login when composer disabled", () => {
      const headers = getAuthHeaders({
        enableComposer: false,
        authType: "none",
        isAutoLogin: true,
        apiKey: "test-key", // pragma: allowlist secret
      });
      expect(headers).toBe("");
    });

    it("returns api key headers when composer disabled and no auto login", () => {
      const headers = getAuthHeaders({
        enableComposer: false,
        authType: "none",
        isAutoLogin: false,
        apiKey: "my-key", // pragma: allowlist secret
      });
      expect(headers).toContain("x-api-key");
      expect(headers).toContain("my-key");
    });

    it("returns empty string for none auth type when composer enabled", () => {
      const headers = getAuthHeaders({
        enableComposer: true,
        authType: "none",
        isAutoLogin: false,
        apiKey: "test-key", // pragma: allowlist secret
      });
      expect(headers).toBe("");
    });

    it("returns api key headers for apikey auth type when composer enabled", () => {
      const headers = getAuthHeaders({
        enableComposer: true,
        authType: "apikey",
        isAutoLogin: false,
        apiKey: "secure-key", // pragma: allowlist secret
      });
      expect(headers).toContain("x-api-key");
      expect(headers).toContain("secure-key");
    });

    it("uses YOUR_API_KEY placeholder when no apiKey provided", () => {
      const headers = getAuthHeaders({
        enableComposer: true,
        authType: "apikey",
        isAutoLogin: false,
      });
      expect(headers).toContain("YOUR_API_KEY");
    });
  });

  describe("buildMcpServerJson", () => {
    it("builds valid JSON for macoslinux platform", () => {
      const json = buildMcpServerJson({
        folderName: "test",
        selectedPlatform: "macoslinux",
        apiUrl: "https://api.test.com",
        isOAuthProject: false,
        authHeadersFragment: "",
      });

      expect(json).toContain('"mcpServers"');
      expect(json).toContain('"lf-test"');
      expect(json).toContain('"command": "uvx"');
      expect(json).toContain('"mcp-proxy"');
    });

    it("builds JSON with wsl command and uvx arg for WSL platform", () => {
      const json = buildMcpServerJson({
        folderName: "wslproj",
        selectedPlatform: "wsl",
        apiUrl: "https://api.test.com",
        isOAuthProject: false,
        authHeadersFragment: "",
      });

      expect(json).toContain('"command": "wsl"');
      expect(json).toContain('"uvx"');
    });

    it("builds JSON with cmd for windows platform", () => {
      const json = buildMcpServerJson({
        folderName: "project",
        selectedPlatform: "windows",
        apiUrl: "https://api.test.com",
        isOAuthProject: false,
        authHeadersFragment: "",
      });

      expect(json).toContain('"command": "cmd"');
      expect(json).toContain('"/c"');
      expect(json).toContain('"uvx"');
    });

    it("uses mcp-composer for OAuth projects", () => {
      const json = buildMcpServerJson({
        folderName: "oauth-proj",
        selectedPlatform: "macoslinux",
        apiUrl: "https://api.test.com",
        isOAuthProject: true,
        authHeadersFragment: "",
      });

      expect(json).toContain('"mcp-composer"');
      expect(json).toContain('"--mode"');
      expect(json).toContain('"stdio"');
      expect(json).toContain('"--sse-url"');
      expect(json).toContain('"oauth"');
    });

    it("includes auth headers in args", () => {
      const json = buildMcpServerJson({
        folderName: "secure",
        selectedPlatform: "macoslinux",
        apiUrl: "https://api.test.com",
        isOAuthProject: false,
        authHeadersFragment: '"--headers","x-api-key","test-key"',
      });

      expect(json).toContain('"--headers"');
      expect(json).toContain('"x-api-key"');
      expect(json).toContain('"test-key"');
    });
  });

  describe("mapFlowsToTools", () => {
    it("maps raw flows to tool format", () => {
      const flows = [
        {
          id: "1",
          name: "Flow One",
          description: "Description one",
          action_name: "flow_one",
          action_description: "Action desc",
          mcp_enabled: true,
        },
      ];

      const tools = mapFlowsToTools(flows);

      expect(tools).toHaveLength(1);
      expect(tools[0]).toMatchObject({
        id: "1",
        name: "flow_one",
        description: "Action desc",
        display_name: "Flow One",
        display_description: "Description one",
        status: true,
        tags: ["Flow One"],
      });
    });

    it("handles empty array", () => {
      const tools = mapFlowsToTools([]);
      expect(tools).toEqual([]);
    });

    it("handles undefined input", () => {
      const tools = mapFlowsToTools();
      expect(tools).toEqual([]);
    });

    it("handles flows with missing optional fields", () => {
      const flows: Array<{ id: string; name?: string; action_name?: string }> =
        [
          {
            id: "1",
          },
        ];

      const tools = mapFlowsToTools(flows);

      expect(tools[0]).toMatchObject({
        id: "1",
        name: "",
        description: "",
        status: false,
      });
    });
  });

  describe("extractInstalledClientNames", () => {
    it("extracts names of installed clients", () => {
      const data = [
        { name: "cursor", installed: true },
        { name: "claude", installed: false },
        { name: "windsurf", installed: true },
      ];

      const names = extractInstalledClientNames(data);

      expect(names).toEqual(["cursor", "windsurf"]);
    });

    it("filters out clients without name", () => {
      const data = [
        { name: "cursor", installed: true },
        { installed: true }, // no name
      ];

      const names = extractInstalledClientNames(data);

      expect(names).toEqual(["cursor"]);
    });

    it("returns empty array for undefined input", () => {
      const names = extractInstalledClientNames(undefined);
      expect(names).toEqual([]);
    });

    it("returns empty array when no clients installed", () => {
      const data = [
        { name: "cursor", installed: false },
        { name: "claude", installed: false },
      ];

      const names = extractInstalledClientNames(data);
      expect(names).toEqual([]);
    });
  });

  describe("createSyntaxHighlighterStyle", () => {
    it("returns dark mode colors", () => {
      const style = createSyntaxHighlighterStyle(true);

      expect(style["hljs-string"].color).toBe("hsla(158, 64%, 52%, 1)");
      expect(style["hljs-attr"].color).toBe("hsla(329, 86%, 70%, 1)");
    });

    it("returns light mode colors", () => {
      const style = createSyntaxHighlighterStyle(false);

      expect(style["hljs-string"].color).toBe("#059669");
      expect(style["hljs-attr"].color).toBe("#DB2777");
    });
  });
});
