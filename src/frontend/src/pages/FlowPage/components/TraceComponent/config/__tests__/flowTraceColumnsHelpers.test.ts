import {
  coerceNumber,
  formatObjectValue,
  formatRunValue,
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
