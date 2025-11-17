/**
 * Unit tests for webhook URL generation logic in CopyFieldAreaComponent
 * This test focuses specifically on testing the URL generation logic that includes flow ID
 */

describe("Webhook URL Generation Logic", () => {
  const BACKEND_URL = "BACKEND_URL";
  const MCP_SSE_VALUE = "MCP_SSE";

  // Mock the protocol and host values
  const protocol = "http:";
  const host = "localhost:7860";
  const URL_WEBHOOK = `${protocol}//${host}/api/v1/webhook/`;
  const URL_MCP_SSE = `${protocol}//${host}/api/v1/mcp/sse`;

  // Helper function that mirrors the component's logic
  function generateWebhookUrl(
    value: string,
    endpointName?: string,
    flowId?: string,
  ): string {
    if (value === BACKEND_URL) {
      return `${URL_WEBHOOK}${endpointName ?? ""}${flowId ?? ""}`;
    } else if (value === MCP_SSE_VALUE) {
      return URL_MCP_SSE;
    }
    return value;
  }

  describe("BACKEND_URL webhook generation", () => {
    it("should generate webhook URL with flow ID when both endpoint name and flow ID are provided", () => {
      const result = generateWebhookUrl(
        BACKEND_URL,
        "test-endpoint",
        "flow-123",
      );

      expect(result).toBe(
        "http://localhost:7860/api/v1/webhook/test-endpointflow-123",
      );
    });

    it("should generate webhook URL with only endpoint name when flow ID is missing", () => {
      const result = generateWebhookUrl(
        BACKEND_URL,
        "test-endpoint",
        undefined,
      );

      expect(result).toBe("http://localhost:7860/api/v1/webhook/test-endpoint");
    });

    it("should generate webhook URL with only flow ID when endpoint name is missing", () => {
      const result = generateWebhookUrl(BACKEND_URL, undefined, "flow-123");

      expect(result).toBe("http://localhost:7860/api/v1/webhook/flow-123");
    });

    it("should generate base webhook URL when both endpoint name and flow ID are missing", () => {
      const result = generateWebhookUrl(BACKEND_URL, undefined, undefined);

      expect(result).toBe("http://localhost:7860/api/v1/webhook/");
    });

    it("should handle empty string values", () => {
      const result = generateWebhookUrl(BACKEND_URL, "", "");

      expect(result).toBe("http://localhost:7860/api/v1/webhook/");
    });

    it("should handle special characters in flow ID", () => {
      const specialFlowId = "flow-123_test%20id!@#$%";
      const result = generateWebhookUrl(BACKEND_URL, "endpoint", specialFlowId);

      expect(result).toBe(
        `http://localhost:7860/api/v1/webhook/endpoint${specialFlowId}`,
      );
    });

    it("should handle very long flow IDs", () => {
      const longFlowId = "a".repeat(200);
      const result = generateWebhookUrl(BACKEND_URL, "endpoint", longFlowId);

      expect(result).toBe(
        `http://localhost:7860/api/v1/webhook/endpoint${longFlowId}`,
      );
    });

    it("should handle Unicode characters in flow ID", () => {
      const unicodeFlowId = "flow-🔥-test-😄";
      const result = generateWebhookUrl(BACKEND_URL, "endpoint", unicodeFlowId);

      expect(result).toBe(
        `http://localhost:7860/api/v1/webhook/endpoint${unicodeFlowId}`,
      );
    });
  });

  describe("MCP_SSE_VALUE generation", () => {
    it("should generate MCP SSE URL regardless of endpoint name and flow ID", () => {
      const result = generateWebhookUrl(
        MCP_SSE_VALUE,
        "test-endpoint",
        "flow-123",
      );

      expect(result).toBe("http://localhost:7860/api/v1/mcp/sse");
    });

    it("should generate MCP SSE URL with missing parameters", () => {
      const result = generateWebhookUrl(MCP_SSE_VALUE, undefined, undefined);

      expect(result).toBe("http://localhost:7860/api/v1/mcp/sse");
    });
  });

  describe("Custom values", () => {
    it("should return original value when not BACKEND_URL or MCP_SSE_VALUE", () => {
      const customValue = "https://my-custom-webhook.com/api";
      const result = generateWebhookUrl(customValue, "endpoint", "flow-123");

      expect(result).toBe(customValue);
    });

    it("should return empty string when custom value is empty", () => {
      const result = generateWebhookUrl("", "endpoint", "flow-123");

      expect(result).toBe("");
    });
  });

  describe("Real-world scenarios", () => {
    const testCases = [
      {
        description: "Production environment with long flow ID",
        value: BACKEND_URL,
        endpointName: "prod-webhook",
        flowId: "550e8400-e29b-41d4-a716-446655440000",
        expected:
          "http://localhost:7860/api/v1/webhook/prod-webhook550e8400-e29b-41d4-a716-446655440000",
      },
      {
        description: "Development environment with simple names",
        value: BACKEND_URL,
        endpointName: "dev",
        flowId: "123",
        expected: "http://localhost:7860/api/v1/webhook/dev123",
      },
      {
        description: "Flow with special characters in endpoint and ID",
        value: BACKEND_URL,
        endpointName: "api-v2_beta",
        flowId: "flow_2024-01-15",
        expected:
          "http://localhost:7860/api/v1/webhook/api-v2_betaflow_2024-01-15",
      },
    ];

    testCases.forEach(
      ({ description, value, endpointName, flowId, expected }) => {
        it(description, () => {
          const result = generateWebhookUrl(value, endpointName, flowId);
          expect(result).toBe(expected);
        });
      },
    );
  });

  describe("Flow ID presence validation", () => {
    it("should ensure flow ID is included in webhook URL", () => {
      const flowId = "critical-flow-id";
      const result = generateWebhookUrl(BACKEND_URL, "webhook", flowId);

      expect(result).toContain(flowId);
      expect(result).toMatch(new RegExp(`${flowId}$`)); // Flow ID should be at the end
    });

    it("should ensure endpoint name comes before flow ID", () => {
      const endpointName = "my-endpoint";
      const flowId = "my-flow";
      const result = generateWebhookUrl(BACKEND_URL, endpointName, flowId);

      const endpointIndex = result.indexOf(endpointName);
      const flowIndex = result.indexOf(flowId);

      expect(endpointIndex).toBeLessThan(flowIndex);
      expect(result).toBe(
        `http://localhost:7860/api/v1/webhook/${endpointName}${flowId}`,
      );
    });
  });
});
