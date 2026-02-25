import {
  formatCost,
  formatJsonData,
  formatSpanDetailLatency,
  formatSpanNodeLatency,
  formatTokens,
  getSpanIcon,
  getSpanTypeLabel,
  getStatusVariant,
} from "../traceViewHelpers";

describe("traceViewHelpers", () => {
  describe("getSpanIcon", () => {
    it("returns icon names for known types", () => {
      expect(getSpanIcon("agent")).toBe("Bot");
      expect(getSpanIcon("chain")).toBe("Link");
      expect(getSpanIcon("retriever")).toBe("Search");
    });
  });

  describe("getStatusVariant", () => {
    it("maps status to badge variants", () => {
      expect(getStatusVariant("success")).toBe("successStatic");
      expect(getStatusVariant("error")).toBe("errorStatic");
      expect(getStatusVariant("running")).toBe("secondaryStatic");
    });
  });

  describe("formatSpanNodeLatency", () => {
    it("formats ms and seconds", () => {
      expect(formatSpanNodeLatency(450)).toBe("450ms");
      expect(formatSpanNodeLatency(1500)).toBe("1.5s");
    });
  });

  describe("formatTokens", () => {
    it("formats token counts", () => {
      expect(formatTokens(12)).toBe("12");
      expect(formatTokens(1250)).toBe("1.3k");
    });

    it("returns null for empty input", () => {
      expect(formatTokens(undefined)).toBeNull();
      expect(formatTokens(0)).toBeNull();
    });
  });

  describe("getSpanTypeLabel", () => {
    it("returns display labels", () => {
      expect(getSpanTypeLabel("llm")).toBe("LLM");
      expect(getSpanTypeLabel("tool")).toBe("Tool");
    });
  });

  describe("formatCost", () => {
    it("formats costs with thresholds", () => {
      expect(formatCost(undefined)).toBe("$0.00");
      expect(formatCost(0)).toBe("$0.00");
      expect(formatCost(0.005)).toBe("$0.005000");
      expect(formatCost(0.12)).toBe("$0.1200");
    });
  });

  describe("formatSpanDetailLatency", () => {
    it("formats seconds and minutes", () => {
      expect(formatSpanDetailLatency(1500)).toBe("1.50s");
      expect(formatSpanDetailLatency(120000)).toBe("2.00m");
    });
  });

  describe("formatJsonData", () => {
    it("stringifies objects", () => {
      expect(formatJsonData({ a: 1 })).toBe('{\n  "a": 1\n}');
    });

    it("falls back to String on circular data", () => {
      const obj: { self?: unknown } = {};
      obj.self = obj;
      expect(formatJsonData(obj)).toBe("[object Object]");
    });
  });
});
