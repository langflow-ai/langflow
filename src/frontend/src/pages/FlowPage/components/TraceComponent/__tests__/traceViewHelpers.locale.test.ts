import i18n from "@/i18n";
import { formatDateLabel } from "../traceViewHelpers";

describe("formatDateLabel", () => {
  const original = i18n.language;

  afterEach(() => {
    i18n.language = original;
  });

  it("should return the input when it is not a date", () => {
    expect(formatDateLabel("not a date")).toBe("not a date");
  });

  // A module-level Intl formatter would have frozen whichever language the app
  // started in; the label has to follow the language it is rendered next to.
  it("should label a date in the language the UI is showing", () => {
    i18n.language = "en";
    const english = formatDateLabel("2026-08-27");
    i18n.language = "pt";
    const portuguese = formatDateLabel("2026-08-27");

    expect(english).not.toBe(portuguese);
    expect(english).toMatch(/Aug/);
    expect(portuguese).toMatch(/ago/);
  });
});
