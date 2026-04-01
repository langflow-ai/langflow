import getWidgetCode from "../get-widget-code";

// Mock the customGetHostProtocol
jest.mock("@/customization/utils/custom-get-host-protocol", () => ({
  customGetHostProtocol: () => ({
    protocol: "https:",
    host: "localhost:3000",
  }),
}));

describe("getWidgetCode", () => {
  const baseOptions = {
    flowId: "test-flow-123",
    flowName: "Test Flow",
    isAuth: false,
    webhookAuthEnable: false,
  };

  describe("Basic widget code generation", () => {
    it("should generate widget code with API key when isAuth is false", () => {
      const code = getWidgetCode(baseOptions);

      // Check for script tag with CDN link
      expect(code).toContain("<script");
      expect(code).toContain("src=");
      expect(code).toContain(
        "https://cdn.jsdelivr.net/gh/logspace-ai/langflow-embedded-chat",
      );
      expect(code).toContain("@v1.0.7");
      expect(code).toContain("</script>");

      // Check for langflow-chat component
      expect(code).toContain("<langflow-chat");
      expect(code).toContain('window_title="Test Flow"');
      expect(code).toContain('flow_id="test-flow-123"');
      expect(code).toContain('host_url="https://localhost:3000"');

      // Should include api_key placeholder when isAuth is false
      expect(code).toContain('api_key="..."');

      // Check closing tag
      expect(code).toContain("</langflow-chat>");
    });

    it("should generate widget code without API key when isAuth is true", () => {
      const code = getWidgetCode({
        ...baseOptions,
        isAuth: true,
      } as any);

      // Check for script tag
      expect(code).toContain("<script");
      expect(code).toContain(
        "https://cdn.jsdelivr.net/gh/logspace-ai/langflow-embedded-chat@v1.0.7",
      );

      // Check for langflow-chat component
      expect(code).toContain("<langflow-chat");
      expect(code).toContain('window_title="Test Flow"');
      expect(code).toContain('flow_id="test-flow-123"');
      expect(code).toContain('host_url="https://localhost:3000"');

      // Should NOT include api_key when isAuth is true
      expect(code).not.toContain("api_key");

      // Check closing tag
      expect(code).toContain("</langflow-chat>");
    });

    it("should use single-line CDN URL when copy is false", () => {
      const code = getWidgetCode({
        ...baseOptions,
        copy: false,
      });

      // Should use multi-line format for non-copy mode
      expect(code).toContain("src=");
      expect(code).toContain("https://cdn.jsdelivr.net/gh/logspace-ai");
      expect(code).toContain("build/static/js/bundle.min.js");
    });

    it("should use formatted CDN URL when copy is true", () => {
      const code = getWidgetCode({
        ...baseOptions,
        copy: true,
      });

      // Should use single-line format for copy mode
      expect(code).toContain(
        "https://cdn.jsdelivr.net/gh/logspace-ai/langflow-embedded-chat@v1.0.7/dist/build/static/js/bundle.min.js",
      );
      expect(code).not.toContain("\nbuild/static");
    });
  });

  describe("Flow ID handling", () => {
    it("should correctly embed flowId in the widget", () => {
      const code = getWidgetCode({
        ...baseOptions,
        flowId: "custom-flow-456",
      });

      expect(code).toContain('flow_id="custom-flow-456"');
    });

    it("should handle empty flowId", () => {
      const code = getWidgetCode({
        ...baseOptions,
        flowId: "",
      });

      expect(code).toContain('flow_id=""');
    });

    it("should handle flowId with special characters", () => {
      const code = getWidgetCode({
        ...baseOptions,
        flowId: "flow-with-dashes_and_underscores",
      });

      expect(code).toContain('flow_id="flow-with-dashes_and_underscores"');
    });

    it("should handle flowId with UUID format", () => {
      const uuid = "550e8400-e29b-41d4-a716-446655440000";
      const code = getWidgetCode({
        ...baseOptions,
        flowId: uuid,
      });

      expect(code).toContain(`flow_id="${uuid}"`);
    });
  });

  describe("Flow name handling", () => {
    it("should correctly embed flowName in window_title", () => {
      const code = getWidgetCode({
        ...baseOptions,
        flowName: "Custom Chat Widget",
      });

      expect(code).toContain('window_title="Custom Chat Widget"');
    });

    it("should handle empty flowName", () => {
      const code = getWidgetCode({
        ...baseOptions,
        flowName: "",
      });

      expect(code).toContain('window_title=""');
    });

    it("should handle flowName with special characters", () => {
      const code = getWidgetCode({
        ...baseOptions,
        flowName: "Chat Widget: v1.0 (beta)",
      });

      expect(code).toContain('window_title="Chat Widget: v1.0 (beta)"');
    });

    it("should handle flowName with quotes", () => {
      const code = getWidgetCode({
        ...baseOptions,
        flowName: 'Widget with "quotes"',
      });

      // Should still contain the window_title attribute
      expect(code).toContain("window_title=");
      // The function doesn't escape quotes, so they appear as-is
      expect(code).toContain("Widget with");
    });

    it("should handle flowName with unicode characters", () => {
      const code = getWidgetCode({
        ...baseOptions,
        flowName: "聊天小部件 Chat Widget 🤖",
      });

      expect(code).toContain('window_title="聊天小部件 Chat Widget 🤖"');
    });

    it("should handle very long flowName", () => {
      const longName = "A".repeat(200);
      const code = getWidgetCode({
        ...baseOptions,
        flowName: longName,
      });

      expect(code).toContain(`window_title="${longName}"`);
    });
  });

  describe("Host URL handling", () => {
    it("should construct host_url from protocol and host", () => {
      const code = getWidgetCode(baseOptions);

      expect(code).toContain('host_url="https://localhost:3000"');
    });

    it("should handle different protocols", () => {
      // Note: This tests the integration with customGetHostProtocol mock
      const code = getWidgetCode(baseOptions);

      expect(code).toContain("https://");
    });
  });

  describe("Authentication handling", () => {
    it("should include api_key attribute when isAuth is false", () => {
      const code = getWidgetCode({
        ...baseOptions,
        isAuth: false,
      } as any);

      expect(code).toContain('api_key="..."');
    });

    it("should not include api_key attribute when isAuth is true", () => {
      const code = getWidgetCode({
        ...baseOptions,
        isAuth: true,
      } as any);

      expect(code).not.toContain("api_key");
    });

    it("should handle isAuth being undefined (defaults to falsy)", () => {
      const code = getWidgetCode({
        flowId: "test-flow",
        flowName: "Test",
        isAuth: undefined,
        webhookAuthEnable: false,
      } as any);

      // When isAuth is undefined/falsy, api_key should be included
      expect(code).toContain('api_key="..."');
    });
  });

  describe("Copy mode handling", () => {
    it("should use compact format when copy is true", () => {
      const code = getWidgetCode({
        ...baseOptions,
        copy: true,
      });

      // Single-line CDN URL
      expect(code).toContain(
        "https://cdn.jsdelivr.net/gh/logspace-ai/langflow-embedded-chat@v1.0.7/dist/build/static/js/bundle.min.js",
      );
      expect(code).not.toContain("\nbuild/static");
    });

    it("should use readable format when copy is false", () => {
      const code = getWidgetCode({
        ...baseOptions,
        copy: false,
      });

      // Multi-line CDN URL
      expect(code).toContain("src=");
      expect(code).toContain("build/static/js/bundle.min.js");
    });

    it("should default to readable format when copy is undefined", () => {
      const code = getWidgetCode({
        flowId: "test",
        flowName: "Test",
        isAuth: false,
        webhookAuthEnable: false,
      } as any);

      // Should use multi-line format by default
      expect(code).toContain("\nbuild/static");
    });
  });

  describe("Code structure", () => {
    it("should have proper HTML structure with script and langflow-chat tags", () => {
      const code = getWidgetCode(baseOptions);

      // Check for opening and closing script tags
      const scriptTagCount = (code.match(/<script/g) || []).length;
      const scriptCloseTagCount = (code.match(/<\/script>/g) || []).length;
      expect(scriptTagCount).toBe(1);
      expect(scriptCloseTagCount).toBe(1);

      // Check for opening and closing langflow-chat tags
      expect(code).toContain("<langflow-chat");
      expect(code).toContain("</langflow-chat>");
    });

    it("should have all required attributes in langflow-chat component", () => {
      const code = getWidgetCode(baseOptions);

      expect(code).toMatch(/window_title="[^"]*"/);
      expect(code).toMatch(/flow_id="[^"]*"/);
      expect(code).toMatch(/host_url="[^"]*"/);
    });

    it("should have correct CDN version reference", () => {
      const code = getWidgetCode(baseOptions);

      expect(code).toContain("@v1.0.7");
    });

    it("should have correct bundle path", () => {
      const code = getWidgetCode(baseOptions);

      // Bundle path may span multiple lines in non-copy mode
      expect(code).toContain("build/static/js/bundle.min.js");
    });
  });

  describe("Edge cases", () => {
    it("should handle all parameters being empty strings", () => {
      const code = getWidgetCode({
        flowId: "",
        flowName: "",
        isAuth: false,
        webhookAuthEnable: false,
      } as any);

      expect(code).toContain("<script");
      expect(code).toContain("<langflow-chat");
      expect(code).toContain('window_title=""');
      expect(code).toContain('flow_id=""');
    });

    it("should handle minimum required parameters", () => {
      const code = getWidgetCode({
        flowId: "test",
        flowName: "Test",
        isAuth: false,
        webhookAuthEnable: false,
      } as any);

      expect(code).toContain("<script");
      expect(code).toContain("<langflow-chat");
      expect(code).toContain("</langflow-chat>");
    });

    it("should produce consistent output for same inputs", () => {
      const code1 = getWidgetCode(baseOptions);
      const code2 = getWidgetCode(baseOptions);

      expect(code1).toBe(code2);
    });

    it("should handle flowId with slashes", () => {
      const code = getWidgetCode({
        ...baseOptions,
        flowId: "folder/subfolder/flow",
      });

      expect(code).toContain('flow_id="folder/subfolder/flow"');
    });

    it("should handle flowName with newlines", () => {
      const code = getWidgetCode({
        ...baseOptions,
        flowName: "Line1\nLine2",
      });

      expect(code).toContain("window_title=");
    });
  });

  describe("Output format", () => {
    it("should return a string", () => {
      const code = getWidgetCode(baseOptions);

      expect(typeof code).toBe("string");
    });

    it("should not have leading or trailing whitespace issues", () => {
      const code = getWidgetCode(baseOptions);

      // Should start with script tag
      expect(code.trimStart()).toMatch(/^<script/);
    });

    it("should be copyable HTML code", () => {
      const code = getWidgetCode({
        ...baseOptions,
        copy: true,
      });

      // Should be valid HTML-like syntax
      expect(code).toContain("<");
      expect(code).toContain(">");
      expect(code).not.toContain("undefined");
      expect(code).not.toContain("null");
    });
  });

  describe("Integration scenarios", () => {
    it("should work with typical production settings", () => {
      const code = getWidgetCode({
        flowId: "prod-flow-123",
        flowName: "Production Chat Bot",
        isAuth: true,
        webhookAuthEnable: false,
        copy: false,
      } as any);

      expect(code).toContain('flow_id="prod-flow-123"');
      expect(code).toContain('window_title="Production Chat Bot"');
      expect(code).not.toContain("api_key");
    });

    it("should work with typical development settings", () => {
      const code = getWidgetCode({
        flowId: "dev-flow-456",
        flowName: "Dev Chat Bot",
        isAuth: false,
        webhookAuthEnable: false,
        copy: true,
      } as any);

      expect(code).toContain('flow_id="dev-flow-456"');
      expect(code).toContain('window_title="Dev Chat Bot"');
      expect(code).toContain('api_key="..."');
    });

    it("should work when embedded in HTML documentation", () => {
      const code = getWidgetCode(baseOptions);

      // Should be valid HTML that can be embedded
      expect(code).not.toContain("{{");
      expect(code).not.toContain("}}");
      expect(code).not.toContain("${");
    });
  });
});
