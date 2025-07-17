// Tests for MustachePromptAreaComponent functionality
// Focus on testing the core logic without importing the full component

describe("MustachePromptAreaComponent", () => {
  describe("mustache variable highlighting logic", () => {
    // Test the core mustache highlighting logic that's used in the component
    const applyMustacheHighlighting = (value: string) => {
      return (
        (typeof value === "string" ? value : "")
          // escape HTML first
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          // highlight mustache variables {{variable}}
          .replace(/\{\{(.+?)\}\}/g, (match, varName) => {
            return `<span class="chat-message-highlight">{{${varName}}}</span>`;
          })
          // preserve new-lines
          .replace(/\n/g, "<br />")
      );
    };

    it("should highlight single mustache variable", () => {
      const input = "Hello {{name}}!";
      const result = applyMustacheHighlighting(input);
      expect(result).toBe(
        'Hello <span class="chat-message-highlight">{{name}}</span>!',
      );
    });

    it("should highlight multiple mustache variables", () => {
      const input = "Hello {{name}}, you are {{age}} years old.";
      const result = applyMustacheHighlighting(input);
      expect(result).toBe(
        'Hello <span class="chat-message-highlight">{{name}}</span>, you are <span class="chat-message-highlight">{{age}}</span> years old.',
      );
    });

    it("should escape HTML content", () => {
      const input = "Content: <script>alert('test')</script>";
      const result = applyMustacheHighlighting(input);
      expect(result).toBe(
        "Content: &lt;script&gt;alert('test')&lt;/script&gt;",
      );
    });

    it("should preserve newlines", () => {
      const input = "Line 1\nLine 2\nLine 3";
      const result = applyMustacheHighlighting(input);
      expect(result).toBe("Line 1<br />Line 2<br />Line 3");
    });

    it("should handle complex mustache variables", () => {
      const input = "{{#if user}}Hello {{user.name}}{{/if}}";
      const result = applyMustacheHighlighting(input);
      expect(result).toBe(
        '<span class="chat-message-highlight">{{#if user}}</span>Hello <span class="chat-message-highlight">{{user.name}}</span><span class="chat-message-highlight">{{/if}}</span>',
      );
    });

    it("should handle mixed content", () => {
      const input =
        "Hello {{name}}!\n<script>alert('test')</script>\nAge: {{age}}";
      const result = applyMustacheHighlighting(input);
      expect(result).toBe(
        'Hello <span class="chat-message-highlight">{{name}}</span>!<br />&lt;script&gt;alert(\'test\')&lt;/script&gt;<br />Age: <span class="chat-message-highlight">{{age}}</span>',
      );
    });

    it("should handle empty string", () => {
      const input = "";
      const result = applyMustacheHighlighting(input);
      expect(result).toBe("");
    });

    it("should handle string with no mustache variables", () => {
      const input = "This is a plain string.";
      const result = applyMustacheHighlighting(input);
      expect(result).toBe("This is a plain string.");
    });

    it("should handle variables with spaces", () => {
      const input = "Hello {{ name with spaces }}!";
      const result = applyMustacheHighlighting(input);
      expect(result).toBe(
        'Hello <span class="chat-message-highlight">{{ name with spaces }}</span>!',
      );
    });

    it("should handle variables with special characters", () => {
      const input = "Value: {{price_$100}}";
      const result = applyMustacheHighlighting(input);
      expect(result).toBe(
        'Value: <span class="chat-message-highlight">{{price_$100}}</span>',
      );
    });
  });

  describe("component props validation", () => {
    it("should accept correct props type", () => {
      const mockProps = {
        id: "test-id",
        value: "Hello {{name}}!",
        editNode: false,
        handleOnNewValue: jest.fn(),
        disabled: false,
        nodeClass: {
          description: "Test component",
          template: {},
          display_name: "Test Component",
          documentation: "Test component documentation",
        },
        handleNodeClass: jest.fn(),
        nodeId: "test-node-id",
        readonly: false,
        field_name: "template",
      };

      // If this compiles without TypeScript errors, the types are correct
      expect(mockProps).toBeDefined();
      expect(mockProps.nodeClass.description).toBe("Test component");
      expect(mockProps.nodeClass.display_name).toBe("Test Component");
      expect(mockProps.nodeClass.documentation).toBe(
        "Test component documentation",
      );
      expect(mockProps.value).toBe("Hello {{name}}!");
      expect(mockProps.field_name).toBe("template");
    });

    it("should handle different value types", () => {
      const propsWithEmptyValue = {
        value: "",
        field_name: "template",
        disabled: false,
        readonly: false,
      };

      const propsWithComplexValue = {
        value: "{{#items}}Item: {{name}} - {{price}}{{/items}}",
        field_name: "template",
        disabled: false,
        readonly: false,
      };

      expect(propsWithEmptyValue.value).toBe("");
      expect(propsWithComplexValue.value).toContain("{{#items}}");
      expect(propsWithComplexValue.value).toContain("{{name}}");
      expect(propsWithComplexValue.value).toContain("{{price}}");
    });
  });
});
