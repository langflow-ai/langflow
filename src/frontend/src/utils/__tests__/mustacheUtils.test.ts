import {
  extractMustacheVariables,
  type MustacheValidationResult,
  validateMustacheTemplate,
} from "../mustacheUtils";

describe("mustacheUtils", () => {
  describe("validateMustacheTemplate", () => {
    describe("valid templates", () => {
      it("should return valid for empty string", () => {
        const result = validateMustacheTemplate("");
        expect(result).toEqual({ isValid: true, variables: [] });
      });

      it("should return valid for plain text without variables", () => {
        const result = validateMustacheTemplate("Hello, this is plain text.");
        expect(result).toEqual({ isValid: true, variables: [] });
      });

      it("should return valid for simple variable", () => {
        const result = validateMustacheTemplate("Hello {{name}}!");
        expect(result.isValid).toBe(true);
        expect(result.variables).toEqual(["name"]);
      });

      it("should return valid for multiple different variables", () => {
        const result = validateMustacheTemplate(
          "Hello {{first_name}} {{last_name}}!",
        );
        expect(result.isValid).toBe(true);
        expect(result.variables).toEqual(["first_name", "last_name"]);
      });

      it("should deduplicate repeated variables", () => {
        const result = validateMustacheTemplate(
          "{{name}} is {{name}} and {{name}}",
        );
        expect(result.isValid).toBe(true);
        expect(result.variables).toEqual(["name"]);
      });

      it("should accept variables starting with underscore", () => {
        const result = validateMustacheTemplate("Value: {{_private_var}}");
        expect(result.isValid).toBe(true);
        expect(result.variables).toEqual(["_private_var"]);
      });

      it("should accept variables with numbers", () => {
        const result = validateMustacheTemplate("Value: {{var123}}");
        expect(result.isValid).toBe(true);
        expect(result.variables).toEqual(["var123"]);
      });

      it("should handle multiline templates", () => {
        const template = `
          Hello {{name}},
          Your order {{order_id}} is ready.
          Thanks!
        `;
        const result = validateMustacheTemplate(template);
        expect(result.isValid).toBe(true);
        expect(result.variables).toEqual(["name", "order_id"]);
      });
    });

    describe("dangerous patterns", () => {
      it("should reject triple braces (unescaped HTML)", () => {
        const result = validateMustacheTemplate("{{{unsafe}}}");
        expect(result.isValid).toBe(false);
        expect(result.error).toContain(
          "Complex mustache syntax is not allowed",
        );
        expect(result.variables).toEqual([]);
      });

      it("should reject conditional sections start", () => {
        const result = validateMustacheTemplate(
          "{{#section}}content{{/section}}",
        );
        expect(result.isValid).toBe(false);
        expect(result.error).toContain(
          "Complex mustache syntax is not allowed",
        );
      });

      it("should reject conditional sections end", () => {
        const result = validateMustacheTemplate("{{/section}}");
        expect(result.isValid).toBe(false);
        expect(result.error).toContain(
          "Complex mustache syntax is not allowed",
        );
      });

      it("should reject inverted sections", () => {
        const result = validateMustacheTemplate(
          "{{^inverted}}no value{{/inverted}}",
        );
        expect(result.isValid).toBe(false);
        expect(result.error).toContain(
          "Complex mustache syntax is not allowed",
        );
      });

      it("should reject unescaped variables with &", () => {
        const result = validateMustacheTemplate("{{&unescaped}}");
        expect(result.isValid).toBe(false);
        expect(result.error).toContain(
          "Complex mustache syntax is not allowed",
        );
      });

      it("should reject partials", () => {
        const result = validateMustacheTemplate("{{>partial}}");
        expect(result.isValid).toBe(false);
        expect(result.error).toContain(
          "Complex mustache syntax is not allowed",
        );
      });

      it("should reject comments", () => {
        const result = validateMustacheTemplate("{{! this is a comment }}");
        expect(result.isValid).toBe(false);
        expect(result.error).toContain(
          "Complex mustache syntax is not allowed",
        );
      });

      it("should reject current context", () => {
        const result = validateMustacheTemplate("{{.}}");
        expect(result.isValid).toBe(false);
        expect(result.error).toContain(
          "Complex mustache syntax is not allowed",
        );
      });
    });

    describe("unclosed tags", () => {
      it("should reject unclosed opening braces", () => {
        const result = validateMustacheTemplate("Hello {{name");
        expect(result.isValid).toBe(false);
        expect(result.error).toContain("matching closing braces");
      });

      it("should reject multiple unclosed braces", () => {
        const result = validateMustacheTemplate("{{foo}} and {{bar");
        expect(result.isValid).toBe(false);
        expect(result.error).toContain("matching closing braces");
      });
    });

    describe("invalid variable names", () => {
      it("should reject variable names starting with number", () => {
        const result = validateMustacheTemplate("{{123abc}}");
        expect(result.isValid).toBe(false);
        expect(result.error).toContain("Invalid mustache variable");
      });

      it("should reject variables with spaces", () => {
        const result = validateMustacheTemplate("{{my variable}}");
        expect(result.isValid).toBe(false);
        expect(result.error).toContain("Invalid mustache variable");
      });

      it("should reject variables with special characters", () => {
        const result = validateMustacheTemplate("{{my-variable}}");
        expect(result.isValid).toBe(false);
        expect(result.error).toContain("Invalid mustache variable");
      });

      it("should reject empty braces", () => {
        const result = validateMustacheTemplate("{{}}");
        expect(result.isValid).toBe(false);
        expect(result.error).toContain("Invalid mustache variable");
      });

      it("should reject variables with dots (nested access)", () => {
        const result = validateMustacheTemplate("{{user.name}}");
        expect(result.isValid).toBe(false);
        expect(result.error).toContain("Invalid mustache variable");
      });
    });
  });

  describe("extractMustacheVariables", () => {
    it("should extract variables from valid template", () => {
      const variables = extractMustacheVariables(
        "Hello {{name}}, your {{item}} is ready.",
      );
      expect(variables).toEqual(["name", "item"]);
    });

    it("should return empty array for invalid template", () => {
      const variables = extractMustacheVariables(
        "{{#section}}content{{/section}}",
      );
      expect(variables).toEqual([]);
    });

    it("should return empty array for empty template", () => {
      const variables = extractMustacheVariables("");
      expect(variables).toEqual([]);
    });

    it("should return empty array for template without variables", () => {
      const variables = extractMustacheVariables("Just plain text");
      expect(variables).toEqual([]);
    });

    it("should deduplicate variables", () => {
      const variables = extractMustacheVariables("{{x}} + {{x}} = {{result}}");
      expect(variables).toEqual(["x", "result"]);
    });
  });
});
