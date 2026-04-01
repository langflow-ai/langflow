import { getUniqueFilename } from "../upload-name-utils";

describe("upload-name-utils", () => {
  describe("getUniqueFilename", () => {
    it("returns original name when there is no collision", () => {
      const existing = new Set<string>(["other.txt"]);
      expect(getUniqueFilename("file.txt", existing)).toBe("file.txt");
    });

    it("appends (2) for the first collision", () => {
      const existing = new Set<string>(["file.txt"]);
      expect(getUniqueFilename("file.txt", existing)).toBe("file (2).txt");
    });

    it("increments until it finds an available name", () => {
      const existing = new Set<string>([
        "file.txt",
        "file (2).txt",
        "file (3).txt",
      ]);
      expect(getUniqueFilename("file.txt", existing)).toBe("file (4).txt");
    });

    it("respects an existing numeric suffix on the original name", () => {
      const existing = new Set<string>(["report (2).pdf", "report (3).pdf"]);
      expect(getUniqueFilename("report (2).pdf", existing)).toBe(
        "report (4).pdf",
      );
    });

    it("handles names without extension", () => {
      const existing = new Set<string>(["README"]);
      expect(getUniqueFilename("README", existing)).toBe("README (2)");
    });

    it("treats dotfiles as extensionless names", () => {
      const existing = new Set<string>([".env"]);
      expect(getUniqueFilename(".env", existing)).toBe(".env (2)");
    });
  });
});
