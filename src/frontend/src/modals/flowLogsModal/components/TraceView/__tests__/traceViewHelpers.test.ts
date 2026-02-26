import {
  formatCost,
  formatIOPreview,
  formatJsonData,
  formatSpanDetailLatency,
  formatSpanNodeLatency,
  formatTimestamp,
  formatTokens,
  formatTotalCost,
  formatTotalLatency,
  getSpanIcon,
  getSpanTypeLabel,
  getStatusIconProps,
  getStatusVariant,
} from "../traceViewHelpers";

jest.mock("@/utils/dateTime", () => ({
  formatSmartTimestamp: jest.fn(() => "mocked-timestamp"),
}));

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
      expect(getStatusVariant("ok")).toBe("successStatic");
      expect(getStatusVariant("error")).toBe("errorStatic");
      expect(getStatusVariant("unset")).toBe("secondaryStatic");
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

  describe("formatTotalCost", () => {
    it("formats total cost", () => {
      expect(formatTotalCost(0)).toBe("$0.00");
      expect(formatTotalCost(0.005)).toBe("$0.005000");
      expect(formatTotalCost(0.12)).toBe("$0.1200");
    });
  });

  describe("formatTotalLatency", () => {
    it("formats total latency", () => {
      expect(formatTotalLatency(800)).toBe("800ms");
      expect(formatTotalLatency(1200)).toBe("1.20s");
    });
  });

  describe("formatTimestamp", () => {
    it("delegates to formatSmartTimestamp", () => {
      expect(formatTimestamp("2024-01-01T00:00:00")).toBe("mocked-timestamp");
    });
  });

  describe("formatIOPreview", () => {
    it("returns N/A for null", () => {
      expect(formatIOPreview(null)).toBe("N/A");
    });

    it("truncates string input", () => {
      const value = "a".repeat(200);
      expect(formatIOPreview(value as unknown as Record<string, unknown>)).toBe(
        `${"a".repeat(150)}...`,
      );
    });

    it("returns value from known text fields", () => {
      expect(formatIOPreview({ message: "hello" })).toBe("hello");
    });

    it("returns nested value from known text fields", () => {
      expect(formatIOPreview({ nested: { text: "nested" } })).toBe("nested");
    });

    it("returns Empty for empty object", () => {
      expect(formatIOPreview({})).toBe("Empty");
    });

    it("returns fallback on circular data", () => {
      const obj: { self?: unknown } = {};
      obj.self = obj;
      expect(formatIOPreview(obj)).toBe("[Complex Object]");
    });
  });

  describe("getStatusIconProps", () => {
    it("maps statuses to icons", () => {
      expect(getStatusIconProps("ok")).toEqual({
        colorClass: "text-status-green",
        iconName: "CircleCheck",
        shouldSpin: false,
      });

      expect(getStatusIconProps("error")).toEqual({
        colorClass: "text-status-red",
        iconName: "CircleX",
        shouldSpin: false,
      });

      expect(getStatusIconProps("unset")).toEqual({
        colorClass: "text-muted-foreground",
        iconName: "Loader2",
        shouldSpin: true,
      });
    });
  });
});
