import {
  getFileExtension,
  hasFileExtension,
  isAllowedChatAttachmentFile,
} from "@/utils/file-validation";

describe("file-validation", () => {
  describe("getFileExtension", () => {
    it("returns lowercase extension", () => {
      expect(getFileExtension("Report.PDF")).toBe("pdf");
    });

    it("returns empty string when no extension", () => {
      expect(getFileExtension("README")).toBe("");
    });

    it("returns empty string for trailing dot", () => {
      expect(getFileExtension("file.")).toBe("");
    });
  });

  describe("hasFileExtension", () => {
    it("returns true for normal file name", () => {
      expect(hasFileExtension("a.txt")).toBe(true);
    });

    it("returns false when no dot", () => {
      expect(hasFileExtension("a")).toBe(false);
    });

    it("returns false for trailing dot", () => {
      expect(hasFileExtension("a.")).toBe(false);
    });

    it("returns true for multi-dot extension", () => {
      expect(hasFileExtension("archive.tar.gz")).toBe(true);
    });
  });

  describe("isAllowedChatAttachmentFile", () => {
    it("allows png by extension and mime type", () => {
      const file = new File(["test"], "photo.png", { type: "image/png" });
      expect(isAllowedChatAttachmentFile(file)).toBe(true);
    });

    it("allows bmp by extension and mime type", () => {
      const file = new File(["test"], "photo.bmp", { type: "image/bmp" });
      expect(isAllowedChatAttachmentFile(file)).toBe(true);
    });

    it("blocks unsupported extension even if mime is empty", () => {
      const file = new File(["test"], "payload.exe", { type: "" });
      expect(isAllowedChatAttachmentFile(file)).toBe(false);
    });

    it("blocks unsupported image extension even if mime looks like an image", () => {
      const file = new File(["test"], "photo.gif", { type: "image/gif" });
      expect(isAllowedChatAttachmentFile(file)).toBe(false);
    });

    it("blocks extension spoofing when mime type contradicts image extension", () => {
      const file = new File(["test"], "report.png", {
        type: "application/pdf",
      });
      expect(isAllowedChatAttachmentFile(file)).toBe(false);
    });

    it("allows files without extension when allowed mime is present", () => {
      const file = new File(["test"], "clipboard", { type: "image/png" });
      expect(isAllowedChatAttachmentFile(file)).toBe(true);
    });

    it("uses extension allow-list when mime type is unavailable", () => {
      const file = new File(["test"], "notes.md", { type: "" });
      expect(isAllowedChatAttachmentFile(file)).toBe(true);
    });

    it("allows mdx when mdx mime type is present", () => {
      const file = new File(["# Hello"], "docs.mdx", { type: "text/mdx" });
      expect(isAllowedChatAttachmentFile(file)).toBe(true);
    });

    it("allows non-image allowed mime types", () => {
      const file = new File(["name,age\nAda,32"], "data.csv", {
        type: "text/csv",
      });
      expect(isAllowedChatAttachmentFile(file)).toBe(true);
    });
  });
});
