import i18n from "@/i18n";
import { formatTimestamp } from "../utils";

describe("formatTimestamp", () => {
  const original = i18n.language;

  afterEach(() => {
    i18n.language = original;
  });

  it("should return a fallback for an unparseable date", () => {
    expect(formatTimestamp("not a date")).toBe("Unknown date");
  });

  // The defect: a version list translated into Portuguese still dated its
  // entries the American way.
  it("should date a version in the language the UI is showing", () => {
    const saved = "2026-08-27T16:45:21Z";

    i18n.language = "en";
    const english = formatTimestamp(saved);
    i18n.language = "pt";
    const portuguese = formatTimestamp(saved);

    expect(english).not.toBe(portuguese);
    expect(english).toMatch(/Aug/);
    expect(portuguese).toMatch(/ago/);
  });
});
