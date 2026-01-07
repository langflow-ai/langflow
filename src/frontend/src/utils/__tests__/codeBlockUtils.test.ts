import { extractLanguage, isCodeBlock } from "../codeBlockUtils";

describe("codeBlockUtils", () => {
  describe("isCodeBlock", () => {
    describe("should return true (block code)", () => {
      it("should_return_true_when_className_has_language_identifier", () => {
        const result = isCodeBlock("language-python", {}, "print('hello')");
        expect(result).toBe(true);
      });

      it("should_return_true_when_className_has_language_javascript", () => {
        const result = isCodeBlock("language-javascript", {}, "const x = 1");
        expect(result).toBe(true);
      });

      it("should_return_true_when_className_has_language_with_other_classes", () => {
        const result = isCodeBlock(
          "hljs language-typescript some-other-class",
          {},
          "const x: number = 1",
        );
        expect(result).toBe(true);
      });

      it("should_return_true_when_props_has_data_language", () => {
        const result = isCodeBlock(
          undefined,
          { "data-language": "python" },
          "print('hello')",
        );
        expect(result).toBe(true);
      });

      it("should_return_true_when_props_has_data_language_empty_string", () => {
        const result = isCodeBlock(undefined, { "data-language": "" }, "code");
        expect(result).toBe(true);
      });

      it("should_return_true_when_content_has_newlines", () => {
        const result = isCodeBlock(undefined, {}, "line1\nline2\nline3");
        expect(result).toBe(true);
      });

      it("should_return_true_when_content_has_single_newline", () => {
        const result = isCodeBlock(undefined, {}, "line1\nline2");
        expect(result).toBe(true);
      });

      it("should_return_true_when_multiple_conditions_are_met", () => {
        const result = isCodeBlock(
          "language-python",
          { "data-language": "python" },
          "def hello():\n    print('world')",
        );
        expect(result).toBe(true);
      });
    });

    describe("should return false (inline code)", () => {
      it("should_return_false_when_no_language_class_no_data_language_no_newlines", () => {
        const result = isCodeBlock(undefined, {}, "inline code");
        expect(result).toBe(false);
      });

      it("should_return_false_when_className_is_empty_string", () => {
        const result = isCodeBlock("", {}, "simple code");
        expect(result).toBe(false);
      });

      it("should_return_false_when_className_has_no_language_prefix", () => {
        const result = isCodeBlock("hljs some-class", {}, "code");
        expect(result).toBe(false);
      });

      it("should_return_false_when_props_is_undefined", () => {
        const result = isCodeBlock(undefined, undefined, "inline");
        expect(result).toBe(false);
      });

      it("should_return_false_when_props_is_empty_object", () => {
        const result = isCodeBlock(undefined, {}, "x = 1");
        expect(result).toBe(false);
      });

      it("should_return_false_when_content_is_single_line", () => {
        const result = isCodeBlock(undefined, {}, "print('hello')");
        expect(result).toBe(false);
      });

      it("should_return_false_when_content_is_empty", () => {
        const result = isCodeBlock(undefined, {}, "");
        expect(result).toBe(false);
      });
    });

    describe("edge cases", () => {
      it("should_handle_language_class_with_numbers", () => {
        const result = isCodeBlock("language-es2020", {}, "code");
        expect(result).toBe(true);
      });

      it("should_handle_content_with_carriage_return_only", () => {
        // \r alone should not be treated as newline for code block
        const result = isCodeBlock(undefined, {}, "line1\rline2");
        expect(result).toBe(false);
      });

      it("should_handle_content_with_crlf", () => {
        const result = isCodeBlock(undefined, {}, "line1\r\nline2");
        expect(result).toBe(true);
      });

      it("should_handle_content_with_trailing_newline_only", () => {
        const result = isCodeBlock(undefined, {}, "single line\n");
        expect(result).toBe(true);
      });

      it("should_handle_content_with_leading_newline_only", () => {
        const result = isCodeBlock(undefined, {}, "\nsingle line");
        expect(result).toBe(true);
      });

      it("should_handle_null_props_gracefully", () => {
        // TypeScript would prevent this, but testing runtime safety
        const result = isCodeBlock(undefined, null as any, "code");
        expect(result).toBe(false);
      });
    });
  });

  describe("extractLanguage", () => {
    it("should_extract_python_from_language_class", () => {
      const result = extractLanguage("language-python");
      expect(result).toBe("python");
    });

    it("should_extract_javascript_from_language_class", () => {
      const result = extractLanguage("language-javascript");
      expect(result).toBe("javascript");
    });

    it("should_extract_language_when_mixed_with_other_classes", () => {
      const result = extractLanguage("hljs language-typescript highlight");
      expect(result).toBe("typescript");
    });

    it("should_return_empty_string_when_no_language_class", () => {
      const result = extractLanguage("hljs some-class");
      expect(result).toBe("");
    });

    it("should_return_empty_string_when_className_is_undefined", () => {
      const result = extractLanguage(undefined);
      expect(result).toBe("");
    });

    it("should_return_empty_string_when_className_is_empty", () => {
      const result = extractLanguage("");
      expect(result).toBe("");
    });

    it("should_handle_language_with_numbers", () => {
      const result = extractLanguage("language-es6");
      expect(result).toBe("es6");
    });

    it("should_extract_first_language_when_multiple_present", () => {
      const result = extractLanguage("language-python language-javascript");
      expect(result).toBe("python");
    });
  });
});
