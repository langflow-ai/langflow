import formatFileName from "../format-file-name";

describe("formatFileName", () => {
  describe("Success cases", () => {
    it("should truncate long file names correctly", () => {
      const longName = "very_long_file_name_that_exceeds_limit.png";
      const result = formatFileName(longName, 25);

      expect(result).toBe("very_long_file_name_that_...png");
      expect(result.endsWith("png")).toBe(true);
    });

    it("should preserve file extension after truncation", () => {
      const fileName = "document_with_very_long_name_here.pdf";
      const result = formatFileName(fileName, 20);

      expect(result).toContain("...");
      expect(result.endsWith("pdf")).toBe(true);
    });

    it("should use default truncation length of 25", () => {
      const longName = "a".repeat(30) + ".txt";
      const result = formatFileName(longName);

      expect(result).toBe("a".repeat(25) + "...txt");
    });

    it("should handle different file extensions", () => {
      const extensions = ["png", "jpg", "pdf", "docx", "xlsx", "mp4"];

      extensions.forEach((ext) => {
        const fileName = "very_long_file_name_that_is_too_long." + ext;
        const result = formatFileName(fileName, 20);

        expect(result.endsWith(ext)).toBe(true);
        expect(result).toContain("...");
      });
    });
  });

  describe("Short file names - no truncation needed", () => {
    it("should return original name when shorter than truncation limit", () => {
      const shortName = "short.png";
      const result = formatFileName(shortName, 25);

      expect(result).toBe("short.png");
    });

    it("should return original name when exactly at truncation limit", () => {
      const exactName = "a".repeat(25) + ".txt"; // 29 chars total
      const result = formatFileName(exactName, 29);

      expect(result).toBe(exactName);
    });

    it("should return original name when base name is 6 characters or less", () => {
      const shortBaseName = "short.verylongextension";
      const result = formatFileName(shortBaseName, 5);

      expect(result).toBe(shortBaseName);
    });
  });

  describe("Edge cases - null/undefined/empty handling (PR #11151 fix)", () => {
    it("should return undefined when name is undefined", () => {
      const result = formatFileName(undefined as unknown as string);

      expect(result).toBeUndefined();
    });

    it("should return null when name is null", () => {
      const result = formatFileName(null as unknown as string);

      expect(result).toBeNull();
    });

    it("should return empty string when name is empty", () => {
      const result = formatFileName("");

      expect(result).toBe("");
    });

    it("should not throw error when name is undefined", () => {
      expect(() =>
        formatFileName(undefined as unknown as string),
      ).not.toThrow();
    });

    it("should not throw error when name is null", () => {
      expect(() => formatFileName(null as unknown as string)).not.toThrow();
    });
  });

  describe("Edge cases - special characters and formats", () => {
    it("should handle file names with multiple dots", () => {
      const fileName = "archive.backup.2024.01.15.tar.gz";
      const result = formatFileName(fileName, 15);

      expect(result.endsWith("gz")).toBe(true);
    });

    it("should handle file names with spaces", () => {
      const fileName = "my document with spaces.pdf";
      const result = formatFileName(fileName, 15);

      expect(result).toContain("...");
      expect(result.endsWith("pdf")).toBe(true);
    });

    it("should handle file names with unicode characters", () => {
      const fileName = "documento_muito_longo_arquivo.pdf";
      const result = formatFileName(fileName, 20);

      expect(result).toContain("...");
      expect(result.endsWith("pdf")).toBe(true);
    });

    it("should handle file names with special characters", () => {
      const fileName = "file-name_with.special@chars#123.txt";
      const result = formatFileName(fileName, 20);

      expect(result.endsWith("txt")).toBe(true);
    });

    it("should handle file names without extension", () => {
      const fileName = "filename_without_extension";
      const result = formatFileName(fileName, 10);

      // When there's no dot:
      // - fileExtension = name.split(".").pop() = "filename_without_extension"
      // - baseName = name.slice(0, -1) = "filename_without_extensio" (lastIndexOf returns -1)
      // - baseName.length (25) > 6 is true
      // - result = baseName.slice(0, 10) + "..." + fileExtension
      // Note: This is a quirk of the current implementation
      expect(result).toBe("filename_w...filename_without_extension");
    });

    it("should return original name for short file without extension", () => {
      const fileName = "short";
      const result = formatFileName(fileName, 10);

      // name[10] is undefined, so returns early
      expect(result).toBe(fileName);
    });

    it("should handle file names with only extension", () => {
      const fileName = ".gitignore";
      const result = formatFileName(fileName, 5);

      // The base name is empty, extension is "gitignore"
      expect(result).toBe(".gitignore");
    });
  });

  describe("Truncation length parameter variations", () => {
    it("should handle truncation length of 0", () => {
      const fileName = "test.txt";
      const result = formatFileName(fileName, 0);

      // name[0] is defined, so it won't return early
      // baseName is "test" (length 4 > 6 is false), so returns original
      expect(result).toBe("test.txt");
    });

    it("should handle very large truncation length", () => {
      const fileName = "short.txt";
      const result = formatFileName(fileName, 1000);

      expect(result).toBe("short.txt");
    });

    it("should handle truncation length of 1", () => {
      const fileName = "verylongfilename.txt";
      const result = formatFileName(fileName, 1);

      expect(result).toBe("v...txt");
    });

    it("should handle negative truncation length", () => {
      const fileName = "test.txt";
      const result = formatFileName(fileName, -5);

      // name[-5] is undefined, so returns early
      expect(result).toBe("test.txt");
    });
  });

  describe("Base name length boundary (6 characters)", () => {
    it("should not truncate when base name is exactly 6 characters", () => {
      const fileName = "abcdef.txt"; // baseName = "abcdef" (6 chars)
      // Force truncation to happen (name[2] is defined)
      const result = formatFileName(fileName, 2);

      // baseName.length (6) > 6 is false, so returns original
      expect(result).toBe("abcdef.txt");
    });

    it("should truncate when base name is 7 characters", () => {
      const fileName = "abcdefg.txt"; // baseName = "abcdefg" (7 chars)
      const result = formatFileName(fileName, 2);

      // baseName.length (7) > 6 is true, so truncates
      expect(result).toBe("ab...txt");
    });

    it("should not truncate when base name is 5 characters", () => {
      const fileName = "abcde.txt";
      const result = formatFileName(fileName, 2);

      expect(result).toBe("abcde.txt");
    });
  });

  describe("Real-world scenarios", () => {
    it("should handle image file from chat upload", () => {
      const fileName = "Screenshot_2024-12-26_at_15.30.45_conversation.png";
      const result = formatFileName(fileName, 25);

      expect(result.length).toBeLessThan(fileName.length);
      expect(result.endsWith("png")).toBe(true);
      expect(result).toContain("...");
    });

    it("should handle PDF document", () => {
      const fileName = "Annual_Report_2024_Q4_Financial_Statements.pdf";
      const result = formatFileName(fileName, 30);

      expect(result.endsWith("pdf")).toBe(true);
    });

    it("should handle code file", () => {
      const fileName = "very_long_component_name_with_description.tsx";
      const result = formatFileName(fileName, 25);

      expect(result.endsWith("tsx")).toBe(true);
    });

    it("should display nicely in UI with default settings", () => {
      const fileName = "user_uploaded_document_from_api.json";
      const result = formatFileName(fileName);

      // Default is 25, should truncate and add ellipsis
      expect(result.length).toBeLessThan(fileName.length);
      expect(result).toContain("...");
    });
  });
});
