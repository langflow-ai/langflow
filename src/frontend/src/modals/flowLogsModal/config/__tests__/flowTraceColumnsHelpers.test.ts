import {
  coerceNumber,
  formatLatency,
  formatObjectValue,
  formatRunValue,
  isNegativeStatus,
  isPositiveStatus,
  pickFirstNumber,
} from "../flowTraceColumnsHelpers";

describe("flowTraceColumnsHelpers", () => {
  describe("formatObjectValue", () => {
    it("returns empty string for nullish values", () => {
      expect(formatObjectValue(null)).toBe("");
      expect(formatObjectValue(undefined)).toBe("");
    });

    it("stringifies plain objects", () => {
      expect(formatObjectValue({ a: 1 })).toBe('{"a":1}');
    });

    it("falls back to String for circular objects", () => {
      const obj: { self?: unknown } = {};
      obj.self = obj;
      expect(formatObjectValue(obj)).toBe("[object Object]");
    });
  });

  describe("coerceNumber", () => {
    it("returns numbers and numeric strings", () => {
      expect(coerceNumber(12)).toBe(12);
      expect(coerceNumber(" 12 ")).toBe(12);
    });

    it("returns null for non-numeric input", () => {
      expect(coerceNumber("abc")).toBeNull();
      expect(coerceNumber("")).toBeNull();
      expect(coerceNumber(undefined)).toBeNull();
    });
  });

  describe("pickFirstNumber", () => {
    it("returns the first valid number", () => {
      expect(pickFirstNumber("", "5", 7)).toBe(5);
    });

    it("returns null when none are valid", () => {
      expect(pickFirstNumber("", undefined, "nope")).toBeNull();
    });
  });

  describe("formatLatency", () => {
    it("formats milliseconds and seconds", () => {
      expect(formatLatency(532)).toBe("532 ms");
      expect(formatLatency(1500)).toBe("1.50 s");
    });

    it("returns empty string for invalid input", () => {
      expect(formatLatency(null)).toBe("");
      expect(formatLatency(Number.NaN)).toBe("");
    });
  });

  describe("status helpers", () => {
    it("detects negative statuses", () => {
      expect(isNegativeStatus("error")).toBe(true);
      expect(isNegativeStatus("Exception: boom")).toBe(true);
    });

    it("detects positive statuses", () => {
      expect(isPositiveStatus("success")).toBe(true);
      expect(isPositiveStatus("Completed")).toBe(true);
    });
  });

  describe("formatRunValue", () => {
    it("combines name and id when both exist", () => {
      expect(formatRunValue("Flow", "123")).toBe("Flow - 123");
    });

    it("returns only provided value when one is missing", () => {
      expect(formatRunValue("Flow", null)).toBe("Flow");
      expect(formatRunValue(null, "123")).toBe("123");
    });
  });
});
