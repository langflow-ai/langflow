import i18n from "@/i18n";
import { formatTimestamp, protectedReasonText } from "../utils";

describe("protectedReasonText", () => {
  const t = i18n.t.bind(i18n) as Parameters<typeof protectedReasonText>[1];

  it.each([
    ["evaluation", "An evaluation uses this version, so it can't be deleted."],
    [
      "admin-upgrade-repair",
      "This version is a recovery point from an upgrade repair, so it can't be deleted.",
    ],
    ["Pinned by release.", "Pinned by release. This version can't be deleted."],
    ["toString", "toString. This version can't be deleted."],
    [null, "This version is protected and can't be deleted."],
    ["  ", "This version is protected and can't be deleted."],
  ])("explains the reason %p", (reason, expected) => {
    expect(protectedReasonText(reason, t)).toBe(expected);
  });
});

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
