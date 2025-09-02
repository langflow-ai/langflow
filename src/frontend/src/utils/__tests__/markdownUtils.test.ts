import {
  cleanupTableEmptyCells,
  isMarkdownTable,
  preprocessChatMessage,
} from "../markdownUtils";

describe("markdownUtils", () => {
  describe("isMarkdownTable", () => {
    it("should return true for valid markdown table", () => {
      const table = `| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |`;
      expect(isMarkdownTable(table)).toBe(true);
    });

    it("should return true for table with alignment", () => {
      const table = `| Left | Center | Right |
|:-----|:------:|------:|
| L1   | C1     | R1    |`;
      expect(isMarkdownTable(table)).toBe(true);
    });

    it("should return false for non-table content", () => {
      expect(isMarkdownTable("Just some text")).toBe(false);
      expect(isMarkdownTable("# Header\nSome content")).toBe(false);
    });

    it("should return false for empty or null input", () => {
      expect(isMarkdownTable("")).toBe(false);
      expect(isMarkdownTable("   ")).toBe(false);
    });

    it("should return false for table without separator", () => {
      const invalidTable = `| Header 1 | Header 2 |
| Cell 1   | Cell 2   |`;
      expect(isMarkdownTable(invalidTable)).toBe(false);
    });

    it("should return true for table with extra whitespace", () => {
      const table = `  | Header 1 | Header 2 |
  |----------|----------|
  | Cell 1   | Cell 2   |  `;
      expect(isMarkdownTable(table)).toBe(true);
    });
  });

  describe("cleanupTableEmptyCells", () => {
    it("should remove completely empty rows", () => {
      const table = `| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
|          |          |
| Cell 3   | Cell 4   |`;

      const expected = `| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
| Cell 3   | Cell 4   |`;

      expect(cleanupTableEmptyCells(table)).toBe(expected);
    });

    it("should keep rows with at least one non-empty cell", () => {
      const table = `| Header 1 | Header 2 |
|----------|----------|
| Cell 1   |          |
|          | Cell 2   |`;

      const expected = `| Header 1 | Header 2 |
|----------|----------|
| Cell 1   |          |
|          | Cell 2   |`;

      expect(cleanupTableEmptyCells(table)).toBe(expected);
    });

    it("should preserve separator rows", () => {
      const table = `| Header 1 | Header 2 |
|----------|----------|
|          |          |`;

      const expected = `| Header 1 | Header 2 |
|----------|----------|`;

      expect(cleanupTableEmptyCells(table)).toBe(expected);
    });

    it("should handle mixed content with tables", () => {
      const content = `Some text before

| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
|          |          |

Some text after`;

      const expected = `Some text before

| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |

Some text after`;

      expect(cleanupTableEmptyCells(content)).toBe(expected);
    });

    it("should handle non-table content unchanged", () => {
      const content = `# Header
This is just regular text.
No tables here.`;

      expect(cleanupTableEmptyCells(content)).toBe(content);
    });

    it("should handle empty input", () => {
      expect(cleanupTableEmptyCells("")).toBe("");
      expect(cleanupTableEmptyCells("   \n   \n   ")).toBe("   \n   \n   ");
    });

    it("should handle table with alignment separators", () => {
      const table = `| Left | Center | Right |
|:-----|:------:|------:|
| L1   | C1     | R1    |
|      |        |       |`;

      const expected = `| Left | Center | Right |
|:-----|:------:|------:|
| L1   | C1     | R1    |`;

      expect(cleanupTableEmptyCells(table)).toBe(expected);
    });
  });

  describe("preprocessChatMessage", () => {
    it("should replace <think> tags with backticks", () => {
      const message = "Before <think>thinking</think> after";
      const expected = "Before `<think>`thinking`</think>` after";
      expect(preprocessChatMessage(message)).toBe(expected);
    });

    it("should handle multiple <think> tags", () => {
      const message = "<think>first</think> and <think>second</think>";
      const expected = "`<think>`first`</think>` and `<think>`second`</think>`";
      expect(preprocessChatMessage(message)).toBe(expected);
    });

    it("should clean up tables when present", () => {
      const message = `<think>analyzing</think>

| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
|          |          |`;

      const result = preprocessChatMessage(message);

      // Should replace think tags
      expect(result).toContain("`<think>`analyzing`</think>`");

      // Should remove empty table row
      expect(result).not.toContain("|          |          |");

      // Should keep good content
      expect(result).toContain("| Cell 1   | Cell 2   |");
    });

    it("should handle messages without tables", () => {
      const message = "<think>pondering</think> Just some regular text";
      const expected = "`<think>`pondering`</think>` Just some regular text";
      expect(preprocessChatMessage(message)).toBe(expected);
    });

    it("should handle messages without think tags", () => {
      const message = `| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
|          |          |`;

      const result = preprocessChatMessage(message);
      expect(result).not.toContain("|          |          |");
      expect(result).toContain("| Cell 1   | Cell 2   |");
    });

    it("should handle empty messages", () => {
      expect(preprocessChatMessage("")).toBe("");
      expect(preprocessChatMessage("   ")).toBe("   ");
    });

    it("should handle complex nested scenarios", () => {
      const message = `<think>Let me create a table</think>

| Name | Status | Notes |
|------|--------|-------|
| John | Active | Good  |
|      |        |       |
| Jane | Active |       |

<think>Done</think>`;

      const result = preprocessChatMessage(message);

      // Think tags should be replaced
      expect(result).toContain("`<think>`Let me create a table`</think>`");
      expect(result).toContain("`<think>`Done`</think>`");

      // Empty row should be removed
      expect(result).not.toContain("|      |        |       |");

      // Partial row should be kept
      expect(result).toContain("| Jane | Active |       |");
    });
  });
});
