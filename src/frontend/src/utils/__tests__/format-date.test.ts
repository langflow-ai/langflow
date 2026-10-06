import i18n from "@/i18n";
import { uiLocale } from "../format-date";

describe("uiLocale", () => {
  const original = i18n.language;

  afterEach(() => {
    i18n.language = original;
  });

  it("should report the language the UI is rendered in", () => {
    i18n.language = "pt";

    expect(uiLocale()).toBe("pt");
  });

  // Intl treats `undefined` as "use the runtime's locale", which is a better
  // guess than pinning a language the user never chose.
  it("should defer to the runtime before i18n resolves a language", () => {
    i18n.language = "" as unknown as string;

    expect(uiLocale()).toBeUndefined();
  });

  // The formatting the modal was getting wrong: same instant, two languages.
  it("should drive Intl formatting per language", () => {
    const instant = new Date("2026-08-27T16:45:21Z");
    const options: Intl.DateTimeFormatOptions = {
      month: "numeric",
      day: "numeric",
      timeZone: "UTC",
    };

    i18n.language = "en";
    const english = instant.toLocaleString(uiLocale(), options);
    i18n.language = "pt";
    const portuguese = instant.toLocaleString(uiLocale(), options);

    expect(english).toBe("8/27");
    expect(portuguese).toBe("27/08");
  });
});
