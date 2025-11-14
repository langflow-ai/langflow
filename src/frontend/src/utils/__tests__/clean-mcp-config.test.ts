import {
  cleanMcpConfig,
  type MCPServerConfig,
  type MCPServerValue,
} from "../helpers/clean-mcp-config";

describe("cleanMcpConfig", () => {
  describe("Successful cleaning scenarios", () => {
    it("should clean all sensitive fields from a complete config", () => {
      const input: MCPServerValue = {
        name: "test-server",
        config: {
          command: "npx mcp-server",
          url: "https://api.example.com",
          headers: {
            "x-api-key": "secret-key-123",
            authorization: "Bearer token123",
          },
          env: {
            API_KEY: "secret-env-key",
            DATABASE_PASSWORD: "secret-db-pass",
          },
          args: ["--token", "secret-arg", "--key", "another-secret"],
          api_key: "direct-api-key",
          token: "auth-token",
          access_token: "access-token-123",
          authorization: "Bearer xyz",
        },
      };

      const result = cleanMcpConfig(input);

      // Sensitive fields should be cleared or removed
      expect(result.config?.headers).toEqual({});
      expect(result.config?.env).toEqual({});
      expect(result.config?.args).toEqual([]);
      expect(result.config?.api_key).toBeUndefined();
      expect(result.config?.token).toBeUndefined();
      expect(result.config?.access_token).toBeUndefined();
      expect(result.config?.authorization).toBeUndefined();

      // Non-sensitive fields should be preserved
      expect(result.config?.command).toBe("npx mcp-server");
      expect(result.config?.url).toBe("https://api.example.com");
      expect(result.name).toBe("test-server");
    });

    it("should preserve non-sensitive config fields", () => {
      const input: MCPServerValue = {
        name: "preserve-test",
        config: {
          command: "test-command",
          url: "https://test.com",
          headers: { "x-secret": "remove-this" },
        },
      };

      const result = cleanMcpConfig(input);

      expect(result.config?.command).toBe("test-command");
      expect(result.config?.url).toBe("https://test.com");
      expect(result.config?.headers).toEqual({});
    });

    it("should handle apiKey (camelCase variant)", () => {
      const input: MCPServerValue = {
        name: "camel-case-test",
        config: {
          apiKey: "camel-case-key",
        },
      };

      const result = cleanMcpConfig(input);

      expect(result.config?.apiKey).toBeUndefined();
    });

    it("should handle both api_key and apiKey simultaneously", () => {
      const input: MCPServerValue = {
        name: "both-keys-test",
        config: {
          api_key: "snake-case-key",
          apiKey: "camel-case-key",
        },
      };

      const result = cleanMcpConfig(input);

      expect(result.config?.api_key).toBeUndefined();
      expect(result.config?.apiKey).toBeUndefined();
    });

    it("should preserve server name", () => {
      const input: MCPServerValue = {
        name: "important-server-name",
        config: {
          headers: { "x-secret": "remove" },
        },
      };

      const result = cleanMcpConfig(input);

      expect(result.name).toBe("important-server-name");
    });

    it("should handle additional properties with index signature", () => {
      const input: MCPServerValue = {
        name: "extra-props-test",
        config: {
          headers: { "x-secret": "remove" },
          customField: "should-be-preserved",
        },
        extraProp: "should-also-be-preserved",
      };

      const result = cleanMcpConfig(input);

      expect(result.config?.headers).toEqual({});
      expect(
        (result.config as unknown as Record<string, unknown>)?.customField,
      ).toBe("should-be-preserved");
      expect((result as unknown as Record<string, unknown>).extraProp).toBe(
        "should-also-be-preserved",
      );
    });
  });

  describe("Edge cases - Empty and minimal configs", () => {
    it("should handle config with no sensitive fields", () => {
      const input: MCPServerValue = {
        name: "clean-server",
        config: {
          command: "safe-command",
          url: "https://safe.com",
        },
      };

      const result = cleanMcpConfig(input);

      expect(result.config?.command).toBe("safe-command");
      expect(result.config?.url).toBe("https://safe.com");
      expect(result.name).toBe("clean-server");
    });

    it("should handle MCPServerValue without config", () => {
      const input: MCPServerValue = {
        name: "no-config-server",
      };

      const result = cleanMcpConfig(input);

      expect(result.name).toBe("no-config-server");
      expect(result.config).toBeUndefined();
    });

    it("should handle config with empty objects", () => {
      const input: MCPServerValue = {
        name: "empty-objects",
        config: {
          headers: {},
          env: {},
          args: [],
        },
      };

      const result = cleanMcpConfig(input);

      expect(result.config?.headers).toEqual({});
      expect(result.config?.env).toEqual({});
      expect(result.config?.args).toEqual([]);
    });

    it("should handle config with only headers", () => {
      const input: MCPServerValue = {
        name: "headers-only",
        config: {
          headers: {
            "x-api-key": "secret",
            "user-agent": "test-agent",
          },
        },
      };

      const result = cleanMcpConfig(input);

      expect(result.config?.headers).toEqual({});
    });

    it("should handle config with only env vars", () => {
      const input: MCPServerValue = {
        name: "env-only",
        config: {
          env: {
            SECRET_KEY: "very-secret",
            PUBLIC_VAR: "not-so-secret",
          },
        },
      };

      const result = cleanMcpConfig(input);

      expect(result.config?.env).toEqual({});
    });

    it("should handle config with only args", () => {
      const input: MCPServerValue = {
        name: "args-only",
        config: {
          args: ["--verbose", "--debug", "--api-key=secret"],
        },
      };

      const result = cleanMcpConfig(input);

      expect(result.config?.args).toEqual([]);
    });
  });

  describe("Edge cases - Null and undefined handling", () => {
    it("should handle undefined config gracefully", () => {
      const input: MCPServerValue = {
        name: "undefined-config",
        config: undefined,
      };

      const result = cleanMcpConfig(input);

      expect(result.name).toBe("undefined-config");
      expect(result.config).toBeUndefined();
    });

    it("should handle null values in config fields", () => {
      const input: MCPServerValue = {
        name: "null-fields",
        config: {
          headers: null as unknown as Record<string, string>,
          env: null as unknown as Record<string, string>,
          args: null as unknown as string[],
        },
      };

      const result = cleanMcpConfig(input);

      // Null values should not cause errors
      expect(result.name).toBe("null-fields");
    });

    it("should handle config with falsy values", () => {
      const input: MCPServerValue = {
        name: "falsy-test",
        config: {
          headers: undefined as unknown as Record<string, string>,
          env: undefined as unknown as Record<string, string>,
          args: undefined as unknown as string[],
          api_key: "",
          token: "",
        },
      };

      const result = cleanMcpConfig(input);

      expect(result.name).toBe("falsy-test");
    });
  });

  describe("Edge cases - Type coercion and special values", () => {
    it("should handle non-array args", () => {
      const input: MCPServerValue = {
        name: "non-array-args",
        config: {
          args: "not-an-array" as unknown as string[],
        },
      };

      const result = cleanMcpConfig(input);

      // Should not crash, and args should remain unchanged if not an array
      expect(result.config?.args).toBe("not-an-array");
    });

    it("should handle non-object headers", () => {
      const input: MCPServerValue = {
        name: "non-object-headers",
        config: {
          headers: "not-an-object" as unknown as Record<string, string>,
        },
      };

      const result = cleanMcpConfig(input);

      // Function should handle gracefully
      expect(result.name).toBe("non-object-headers");
    });

    it("should handle config as non-object", () => {
      const input: MCPServerValue = {
        name: "non-object-config",
        config: "not-an-object" as unknown as MCPServerConfig,
      };

      const result = cleanMcpConfig(input);

      // Should return input unchanged when config is not an object
      expect(result.name).toBe("non-object-config");
      expect(result.config).toBe("not-an-object");
    });
  });

  describe("Mutation and immutability", () => {
    it("should mutate the input object (current behavior)", () => {
      const input: MCPServerValue = {
        name: "mutation-test",
        config: {
          headers: { "x-secret": "remove-me" },
          api_key: "secret",
        },
      };

      const result = cleanMcpConfig(input);

      // Current implementation mutates the input
      expect(input.config?.headers).toEqual({});
      expect(input.config?.api_key).toBeUndefined();
      expect(result).toBe(input); // Same reference
    });

    it("should return the same reference", () => {
      const input: MCPServerValue = {
        name: "reference-test",
        config: {
          command: "test",
        },
      };

      const result = cleanMcpConfig(input);

      expect(result).toBe(input);
    });
  });

  describe("Complex scenarios", () => {
    it("should handle nested or complex header values", () => {
      const input: MCPServerValue = {
        name: "complex-headers",
        config: {
          headers: {
            "x-api-key": "secret",
            "x-custom-header": "value",
            authorization: "Bearer token with spaces",
          },
        },
      };

      const result = cleanMcpConfig(input);

      expect(result.config?.headers).toEqual({});
    });

    it("should handle deeply nested env vars", () => {
      const input: MCPServerValue = {
        name: "complex-env",
        config: {
          env: {
            SIMPLE_VAR: "value",
            "COMPLEX.VAR": "nested.value",
            "VAR_WITH_SPECIAL_CHARS!": "special@value#",
          },
        },
      };

      const result = cleanMcpConfig(input);

      expect(result.config?.env).toEqual({});
    });

    it("should handle large number of args", () => {
      const input: MCPServerValue = {
        name: "many-args",
        config: {
          args: Array.from({ length: 100 }, (_, i) => `--arg${i}=value${i}`),
        },
      };

      const result = cleanMcpConfig(input);

      expect(result.config?.args).toEqual([]);
    });

    it("should handle Unicode and special characters in values", () => {
      const input: MCPServerValue = {
        name: "unicode-test-🔐",
        config: {
          headers: {
            "x-key": "secret-🔑",
          },
          env: {
            KEY: "密钥",
          },
          api_key: "クレデンシャル",
        },
      };

      const result = cleanMcpConfig(input);

      expect(result.name).toBe("unicode-test-🔐");
      expect(result.config?.headers).toEqual({});
      expect(result.config?.env).toEqual({});
      expect(result.config?.api_key).toBeUndefined();
    });

    it("should handle config with all possible sensitive fields", () => {
      const input: MCPServerValue = {
        name: "all-sensitive-fields",
        config: {
          headers: { key: "secret" },
          env: { VAR: "secret" },
          args: ["--secret"],
          api_key: "secret1",
          apiKey: "secret2",
          token: "secret3",
          access_token: "secret4",
          authorization: "secret5",
          command: "preserve-me",
        },
      };

      const result = cleanMcpConfig(input);

      // All sensitive fields removed
      expect(result.config?.headers).toEqual({});
      expect(result.config?.env).toEqual({});
      expect(result.config?.args).toEqual([]);
      expect(result.config?.api_key).toBeUndefined();
      expect(result.config?.apiKey).toBeUndefined();
      expect(result.config?.token).toBeUndefined();
      expect(result.config?.access_token).toBeUndefined();
      expect(result.config?.authorization).toBeUndefined();

      // Non-sensitive preserved
      expect(result.config?.command).toBe("preserve-me");
    });
  });

  describe("Real-world scenarios", () => {
    it("should handle typical MCP server export config", () => {
      const input: MCPServerValue = {
        name: "production-mcp-server",
        config: {
          command: "npx @modelcontextprotocol/server-everything",
          args: ["--port", "3000"],
          env: {
            NODE_ENV: "production",
            API_KEY: "prod-secret-key",
          },
          headers: {
            "content-type": "application/json",
            "x-api-key": "header-secret",
          },
        },
      };

      const result = cleanMcpConfig(input);

      expect(result.config?.command).toBe(
        "npx @modelcontextprotocol/server-everything",
      );
      expect(result.config?.args).toEqual([]);
      expect(result.config?.env).toEqual({});
      expect(result.config?.headers).toEqual({});
    });

    it("should handle GitHub MCP server config", () => {
      const input: MCPServerValue = {
        name: "github-mcp",
        config: {
          command: "uvx mcp-server-github",
          env: {
            GITHUB_TOKEN: "ghp_secrettoken123",
          },
        },
      };

      const result = cleanMcpConfig(input);

      expect(result.config?.command).toBe("uvx mcp-server-github");
      expect(result.config?.env).toEqual({});
    });

    it("should handle HTTP-based MCP server", () => {
      const input: MCPServerValue = {
        name: "http-mcp-server",
        config: {
          url: "https://mcp.example.com/sse",
          headers: {
            authorization: "Bearer secret-token",
            "x-api-key": "api-key-123",
          },
        },
      };

      const result = cleanMcpConfig(input);

      expect(result.config?.url).toBe("https://mcp.example.com/sse");
      expect(result.config?.headers).toEqual({});
    });
  });
});
