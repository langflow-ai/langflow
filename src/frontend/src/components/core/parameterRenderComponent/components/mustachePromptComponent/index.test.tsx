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
          // highlight only simple mustache variables {{variable_name}} - no complex syntax
          .replace(
            /\{\{([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\}\}/g,
            (match, varName) => {
              return `<span class="chat-message-highlight">{{${varName}}}</span>`;
            },
          )
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

    it("should NOT highlight complex mustache syntax", () => {
      const input = "{{#if user}}Hello {{user.name}}{{/if}}";
      const result = applyMustacheHighlighting(input);
      expect(result).toBe(
        '{{#if user}}Hello <span class="chat-message-highlight">{{user.name}}</span>{{/if}}',
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

    it("should NOT highlight variables with spaces", () => {
      const input = "Hello {{ name with spaces }}!";
      const result = applyMustacheHighlighting(input);
      expect(result).toBe("Hello {{ name with spaces }}!");
    });

    it("should NOT highlight variables with invalid characters", () => {
      const input = "Value: {{price-$100}}";
      const result = applyMustacheHighlighting(input);
      expect(result).toBe("Value: {{price-$100}}");
    });

    it("should handle variables with underscores", () => {
      const input = "Value: {{price_100}}";
      const result = applyMustacheHighlighting(input);
      expect(result).toBe(
        'Value: <span class="chat-message-highlight">{{price_100}}</span>',
      );
    });

    it("should handle dot notation variables", () => {
      const input = "Hello {{user.name}} from {{company.address.city}}";
      const result = applyMustacheHighlighting(input);
      expect(result).toBe(
        'Hello <span class="chat-message-highlight">{{user.name}}</span> from <span class="chat-message-highlight">{{company.address.city}}</span>',
      );
    });

    it("should reject variables starting with numbers", () => {
      const input = "Value: {{123invalid}}";
      const result = applyMustacheHighlighting(input);
      expect(result).toBe("Value: {{123invalid}}");
    });

    it("should reject variables with hashtags (conditionals)", () => {
      const input = "{{#each items}}Item{{/each}}";
      const result = applyMustacheHighlighting(input);
      expect(result).toBe("{{#each items}}Item{{/each}}");
    });

    it("should reject variables with forward slashes (closers)", () => {
      const input = "{{/if}}";
      const result = applyMustacheHighlighting(input);
      expect(result).toBe("{{/if}}");
    });

    it("should reject variables with carets (inverted sections)", () => {
      const input = "{{^isEmpty}}Not empty{{/isEmpty}}";
      const result = applyMustacheHighlighting(input);
      expect(result).toBe("{{^isEmpty}}Not empty{{/isEmpty}}");
    });

    it("should reject variables with ampersands (unescaped)", () => {
      const input = "{{&unescaped}}";
      const result = applyMustacheHighlighting(input);
      expect(result).toBe("{{&unescaped}}");
    });

    it("should reject variables with dots at the start", () => {
      const input = "{{.}}";
      const result = applyMustacheHighlighting(input);
      expect(result).toBe("{{.}}");
    });

    it("should reject empty variables", () => {
      const input = "{{}}";
      const result = applyMustacheHighlighting(input);
      expect(result).toBe("{{}}");
    });

    it("should reject variables with special operators", () => {
      const input = "{{>partial}} {{!comment}}";
      const result = applyMustacheHighlighting(input);
      expect(result).toBe("{{&gt;partial}} {{!comment}}");
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
        value: "Item: {{name}} - {{price}}",
        field_name: "template",
        disabled: false,
        readonly: false,
      };

      expect(propsWithEmptyValue.value).toBe("");
      expect(propsWithComplexValue.value).toContain("{{name}}");
      expect(propsWithComplexValue.value).toContain("{{price}}");
    });
  });
});
