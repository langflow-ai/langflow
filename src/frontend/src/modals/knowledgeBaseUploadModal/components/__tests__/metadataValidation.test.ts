import {
  filterValidMetadataPairs,
  KEY_PATTERN,
  MAX_KEYS,
  MAX_VALUE_LENGTH,
  validateMetadataPair,
  validateMetadataPairs,
} from "../metadataValidation";

describe("KEY_PATTERN", () => {
  it("matches the documented rule (lowercase / digits / underscore, ≤32)", () => {
    expect(KEY_PATTERN.test("year")).toBe(true);
    expect(KEY_PATTERN.test("dept_name")).toBe(true);
    expect(KEY_PATTERN.test("Year")).toBe(false);
    expect(KEY_PATTERN.test("year-1")).toBe(false);
    expect(KEY_PATTERN.test("a".repeat(32))).toBe(true);
    expect(KEY_PATTERN.test("a".repeat(33))).toBe(false);
  });
});

describe("validateMetadataPair", () => {
  it("treats a fully empty row as ok (not-yet-filled-in)", () => {
    expect(validateMetadataPair("", "")).toEqual({ ok: true });
    expect(validateMetadataPair("   ", "   ")).toEqual({ ok: true });
  });

  it("requires a key when a value is set, and vice versa", () => {
    expect(validateMetadataPair("", "2024")).toEqual({
      ok: false,
      error: "Key is required when a value is set.",
    });
    expect(validateMetadataPair("year", "")).toEqual({
      ok: false,
      error: "Value is required when a key is set.",
    });
  });

  it("rejects keys that fail the pattern", () => {
    expect(validateMetadataPair("Year", "2024")).toEqual({
      ok: false,
      error: "Keys must be 1-32 lowercase letters, digits, or underscores.",
    });
  });

  it("rejects values longer than MAX_VALUE_LENGTH", () => {
    const longValue = "x".repeat(MAX_VALUE_LENGTH + 1);
    expect(validateMetadataPair("year", longValue)).toEqual({
      ok: false,
      error: `Values must be ${MAX_VALUE_LENGTH} characters or fewer.`,
    });
  });

  it("accepts a valid pair", () => {
    expect(validateMetadataPair("year", "2024")).toEqual({ ok: true });
  });
});

describe("validateMetadataPairs", () => {
  it("returns ok with no errors for an empty array", () => {
    expect(validateMetadataPairs([])).toEqual({ ok: true, errors: {} });
  });

  it("ignores fully-empty rows", () => {
    expect(
      validateMetadataPairs([
        { key: "", value: "" },
        { key: "year", value: "2024" },
      ]),
    ).toEqual({ ok: true, errors: {} });
  });

  it("reports per-row errors keyed by index", () => {
    const result = validateMetadataPairs([
      { key: "Year", value: "2024" },
      { key: "ok_key", value: "ok" },
    ]);
    expect(result.ok).toBe(false);
    expect(result.errors[0]).toMatch(/lowercase letters/);
    expect(result.errors[1]).toBeUndefined();
  });

  it("flags duplicate keys on the second occurrence", () => {
    const result = validateMetadataPairs([
      { key: "year", value: "2024" },
      { key: "year", value: "2025" },
    ]);
    expect(result.ok).toBe(false);
    expect(result.errors[0]).toBeUndefined();
    expect(result.errors[1]).toBe("Duplicate key.");
  });

  it("sets setError when the total count exceeds MAX_KEYS", () => {
    const pairs = Array.from({ length: MAX_KEYS + 1 }, (_, i) => ({
      key: `k${i}`,
      value: `v${i}`,
    }));
    const result = validateMetadataPairs(pairs);
    expect(result.ok).toBe(false);
    expect(result.setError).toMatch(/Up to/);
  });
});

describe("filterValidMetadataPairs", () => {
  it("strips invalid, empty, and duplicate-keyed rows, trimming whitespace", () => {
    const out = filterValidMetadataPairs([
      { key: "  year  ", value: "  2024  " },
      { key: "Year", value: "bad" }, // invalid key
      { key: "year", value: "2025" }, // duplicate
      { key: "", value: "" }, // empty
      { key: "dept", value: "eng" },
    ]);
    expect(out).toEqual([
      { key: "year", value: "2024" },
      { key: "dept", value: "eng" },
    ]);
  });
});
