import {
  KEY_PATTERN,
  validateMetadataFilter,
} from "../metadataFilterValidation";

describe("KEY_PATTERN", () => {
  it("accepts lowercase letters, digits, and underscores up to 32 chars", () => {
    expect(KEY_PATTERN.test("year")).toBe(true);
    expect(KEY_PATTERN.test("year_2024")).toBe(true);
    expect(KEY_PATTERN.test("a".repeat(32))).toBe(true);
  });

  it("rejects uppercase, punctuation, spaces, and over-length keys", () => {
    expect(KEY_PATTERN.test("Year")).toBe(false);
    expect(KEY_PATTERN.test("year-2024")).toBe(false);
    expect(KEY_PATTERN.test("year 2024")).toBe(false);
    expect(KEY_PATTERN.test("a".repeat(33))).toBe(false);
    expect(KEY_PATTERN.test("")).toBe(false);
  });
});

describe("validateMetadataFilter", () => {
  it("returns ok with trimmed key and value on a valid input pair", () => {
    expect(validateMetadataFilter("  year  ", "  2024  ")).toEqual({
      ok: true,
      key: "year",
      value: "2024",
    });
  });

  it("rejects an empty key or value with the required-fields message", () => {
    expect(validateMetadataFilter("", "2024")).toEqual({
      ok: false,
      error: "Key and value are required.",
    });
    expect(validateMetadataFilter("year", "   ")).toEqual({
      ok: false,
      error: "Key and value are required.",
    });
  });

  it("rejects a malformed key with the pattern message", () => {
    expect(validateMetadataFilter("Year", "2024")).toEqual({
      ok: false,
      error: "Key must be 1-32 lowercase letters, digits, or underscores.",
    });
  });
});
