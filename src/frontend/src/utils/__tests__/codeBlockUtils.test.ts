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

      // Note: Content with newlines alone is NOT considered a code block.
      // This is intentional to prevent duplicate code block rendering during streaming.
      // react-markdown identifies code blocks through language class or data-language attribute.

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

      it("should_handle_null_props_gracefully", () => {
        // TypeScript would prevent this, but testing runtime safety
        const result = isCodeBlock(undefined, null as any, "code");
        expect(result).toBe(false);
      });

      it("should_return_false_for_content_with_newlines_but_no_language_indicator", () => {
        // Newlines alone should NOT make content a code block
        // This prevents duplicate rendering during streaming
        const result = isCodeBlock(undefined, {}, "line1\nline2\nline3");
        expect(result).toBe(false);
      });

      it("should_return_true_for_content_with_newlines_AND_language_class", () => {
        const result = isCodeBlock(
          "language-python",
          {},
          "def hello():\n    print('world')",
        );
        expect(result).toBe(true);
      });

      it("should_return_true_for_content_with_newlines_AND_data_language", () => {
        const result = isCodeBlock(
          undefined,
          { "data-language": "python" },
          "def hello():\n    print('world')",
        );
        expect(result).toBe(true);
      });
    });

    describe("streaming scenarios", () => {
      it("should_not_treat_partial_streaming_content_as_block", () => {
        // During streaming, content may arrive with newlines but without
        // proper language indicators. This should NOT be treated as a block.
        const partialContent = "def hello():\n    print('world')";
        const result = isCodeBlock(undefined, {}, partialContent);
        expect(result).toBe(false);
      });

      it("should_treat_properly_marked_streaming_content_as_block", () => {
        // When react-markdown properly identifies code, it adds language class
        const partialContent = "def hello():\n    print('world')";
        const result = isCodeBlock("language-python", {}, partialContent);
        expect(result).toBe(true);
      });

      it("should_handle_code_block_without_language_via_data_language", () => {
        // Code blocks without language (```) get data-language attribute
        const content = "some code\nwith newlines";
        const result = isCodeBlock(undefined, { "data-language": "" }, content);
        expect(result).toBe(true);
      });

      it("should_prevent_duplicate_blocks_during_streaming", () => {
        // This test documents the bug fix:
        // During streaming, if content with newlines was treated as a code block,
        // it would cause the same code to appear as multiple blocks.
        // By only using language class and data-language, we prevent this.

        // Scenario: code is being streamed and arrives in chunks with newlines
        const streamingChunk1 =
          "output_data = {\n    'total_iterations': iteration_count,";
        const streamingChunk2 =
          "\n    'termination_reason': termination_reason,\n    'results': results,";

        // Without proper language marker, these should NOT be code blocks
        expect(isCodeBlock(undefined, {}, streamingChunk1)).toBe(false);
        expect(isCodeBlock(undefined, {}, streamingChunk2)).toBe(false);

        // With proper language marker, they should be code blocks
        expect(isCodeBlock("language-python", {}, streamingChunk1)).toBe(true);
        expect(isCodeBlock("language-python", {}, streamingChunk2)).toBe(true);
      });

      it("should_handle_multiline_code_consistently_regardless_of_newline_count", () => {
        // All these should behave the same - only language marker matters
        const singleLine = "print('hello')";
        const twoLines = "x = 1\ny = 2";
        const manyLines = "x = 1\ny = 2\nz = 3\nprint(x + y + z)";

        // Without language marker, all should be inline
        expect(isCodeBlock(undefined, {}, singleLine)).toBe(false);
        expect(isCodeBlock(undefined, {}, twoLines)).toBe(false);
        expect(isCodeBlock(undefined, {}, manyLines)).toBe(false);

        // With language marker, all should be blocks
        expect(isCodeBlock("language-python", {}, singleLine)).toBe(true);
        expect(isCodeBlock("language-python", {}, twoLines)).toBe(true);
        expect(isCodeBlock("language-python", {}, manyLines)).toBe(true);
      });

      it("should_not_create_block_from_text_that_looks_like_code", () => {
        // Text content that happens to look like code should not become a block
        // unless properly marked by the markdown parser
        const codelikeText = `
          "Condition threshold reached"
          if iteration_count >= condition_threshold
          else "Max iterations reached"
        `;
        expect(isCodeBlock(undefined, {}, codelikeText)).toBe(false);
      });

      it("should_handle_incomplete_code_blocks_during_streaming", () => {
        // When streaming, code blocks may be incomplete (missing closing ```)
        // The parser may not assign language class yet
        const incompleteBlock = "def hello():\n    print('world')";
        expect(isCodeBlock(undefined, {}, incompleteBlock)).toBe(false);

        // Once properly parsed, it will have the language class
        expect(isCodeBlock("language-python", {}, incompleteBlock)).toBe(true);
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
