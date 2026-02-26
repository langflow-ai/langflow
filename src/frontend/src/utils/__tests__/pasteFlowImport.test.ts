import {
  getFlowFilesFromClipboard,
  getPastedFlowFile,
  isEditablePasteTarget,
} from "../pasteFlowImport";

function readFileAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}

describe("pasteFlowImport", () => {
  describe("getPastedFlowFile", () => {
    describe("when input is empty or invalid", () => {
      it("should return null for empty string", () => {
        expect(getPastedFlowFile("")).toBeNull();
      });

      it("should return null for whitespace-only string", () => {
        expect(getPastedFlowFile("   \n  ")).toBeNull();
      });

      it("should return null for text exceeding max length", () => {
        const long = "x".repeat(5_000_001);
        expect(getPastedFlowFile(long)).toBeNull();
      });

      it("should return null for invalid JSON", () => {
        expect(getPastedFlowFile("not json")).toBeNull();
        expect(getPastedFlowFile("{ invalid }")).toBeNull();
      });

      it("should return null for valid JSON that is not a flow payload", () => {
        expect(getPastedFlowFile("{}")).toBeNull();
        expect(getPastedFlowFile('{"a":1}')).toBeNull();
        expect(getPastedFlowFile('{"nodes":[]}')).toBeNull();
        expect(getPastedFlowFile('{"edges":[]}')).toBeNull();
      });
    });

    describe("when input is valid flow payload", () => {
      it("should return a File for raw { nodes, edges } payload", async () => {
        const payload = '{"nodes":[],"edges":[]}';
        const result = getPastedFlowFile(payload);
        expect(result).not.toBeNull();
        expect(result).toBeInstanceOf(File);
        expect(result!.name).toMatch(/^pasted-flow-.*\.json$/);
        expect(result!.type).toBe("application/json");
        const content = JSON.parse(await readFileAsText(result!));
        expect(content.data).toEqual({
          nodes: [],
          edges: [],
          viewport: { x: 0, y: 0, zoom: 1 },
        });
      });

      it("should return a File for JSON wrapped in code fence", async () => {
        const payload = '```json\n{"nodes":[],"edges":[]}\n```';
        const result = getPastedFlowFile(payload);
        expect(result).not.toBeNull();
        expect(result).toBeInstanceOf(File);
        const content = JSON.parse(await readFileAsText(result!));
        expect(content.data.nodes).toEqual([]);
        expect(content.data.edges).toEqual([]);
      });

      it("should return a File for payload with flows array", () => {
        const payload = '{"flows":[{"data":{"nodes":[],"edges":[]}}]}';
        const result = getPastedFlowFile(payload);
        expect(result).not.toBeNull();
        expect(result).toBeInstanceOf(File);
      });

      it("should return a File for payload with data.nodes and data.edges", async () => {
        const payload =
          '{"data":{"nodes":[],"edges":[],"viewport":{"x":0,"y":0,"zoom":1}}}';
        const result = getPastedFlowFile(payload);
        expect(result).not.toBeNull();
        expect(result).toBeInstanceOf(File);
        const content = JSON.parse(await readFileAsText(result!));
        expect(content.data.nodes).toEqual([]);
        expect(content.data.edges).toEqual([]);
      });
    });
  });

  describe("getFlowFilesFromClipboard", () => {
    it("should return empty array for null", () => {
      expect(getFlowFilesFromClipboard(null)).toEqual([]);
    });

    it("should return empty array for DataTransfer with no files", () => {
      const dt = { files: { length: 0 } } as unknown as DataTransfer;
      expect(getFlowFilesFromClipboard(dt)).toEqual([]);
    });

    it("should return empty array when files are not JSON", () => {
      const txtFile = new File(["hello"], "readme.txt", { type: "text/plain" });
      const dt = {
        files: {
          length: 1,
          item: (i: number) => (i === 0 ? txtFile : null),
          0: txtFile,
        },
      } as unknown as DataTransfer;
      expect(getFlowFilesFromClipboard(dt)).toEqual([]);
    });

    it("should return and normalize a single .json file", () => {
      const jsonFile = new File(['{"nodes":[]}'], "flow.json", { type: "" });
      const dt = {
        files: {
          length: 1,
          item: (i: number) => (i === 0 ? jsonFile : null),
          0: jsonFile,
        },
      } as unknown as DataTransfer;
      const result = getFlowFilesFromClipboard(dt);
      expect(result).toHaveLength(1);
      expect(result[0].name).toBe("flow.json");
      expect(result[0].type).toBe("application/json");
    });

    it("should return only JSON files when multiple file types are present", () => {
      const jsonFile = new File(['{"nodes":[]}'], "flow.json", {
        type: "application/json",
      });
      const txtFile = new File(["x"], "x.txt", { type: "text/plain" });
      const dt = {
        files: {
          length: 2,
          item: (i: number) => (i === 0 ? jsonFile : i === 1 ? txtFile : null),
          0: jsonFile,
          1: txtFile,
        },
      } as unknown as DataTransfer;
      const result = getFlowFilesFromClipboard(dt);
      expect(result).toHaveLength(1);
      expect(result[0].name).toBe("flow.json");
    });
  });

  describe("isEditablePasteTarget", () => {
    it("should return false for null", () => {
      expect(isEditablePasteTarget(null)).toBe(false);
    });

    it("should return false for non-HTMLElement", () => {
      expect(isEditablePasteTarget(document as unknown as EventTarget)).toBe(
        false,
      );
    });

    it("should return true for HTMLInputElement", () => {
      const input = document.createElement("input");
      expect(isEditablePasteTarget(input)).toBe(true);
    });

    it("should return true for HTMLTextAreaElement", () => {
      const textarea = document.createElement("textarea");
      expect(isEditablePasteTarget(textarea)).toBe(true);
    });

    it("should return true for contentEditable element", () => {
      const div = document.createElement("div");
      div.contentEditable = "true";
      Object.defineProperty(div, "isContentEditable", {
        value: true,
        configurable: true,
      });
      expect(isEditablePasteTarget(div)).toBe(true);
    });

    it("should return false for plain div", () => {
      const div = document.createElement("div");
      expect(isEditablePasteTarget(div)).toBe(false);
    });
  });
});
