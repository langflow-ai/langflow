import i18n, { loadLanguage } from "../i18n";
import en from "../locales/en.json";
import tr from "../locales/tr.json";

const enTranslations = en as Record<string, string>;
const trTranslations = tr as Record<string, string>;

const getPlaceholders = (value: string): string[] =>
  Array.from(
    value.matchAll(/\{\{[^}]+}}/g),
    ([placeholder]) => placeholder,
  ).sort();

describe("loadLanguage", () => {
  beforeEach(() => {
    // Remove any bundles added by previous tests so each test starts clean.
    jest.resetModules();
  });

  it("resolves without throwing for an unknown locale", async () => {
    await expect(loadLanguage("xx")).resolves.toBeUndefined();
  });

  it("does not register a bundle for an unknown locale", async () => {
    await loadLanguage("xx");
    expect(i18n.hasResourceBundle("xx", "translation")).toBe(false);
  });

  it("returns early without throwing for 'en'", async () => {
    await expect(loadLanguage("en")).resolves.toBeUndefined();
  });

  it("registers the Turkish locale bundle", async () => {
    await loadLanguage("tr");
    expect(i18n.hasResourceBundle("tr", "translation")).toBe(true);
    expect(i18n.t("settings.languageTitle", { lng: "tr" })).toBe("Dil");
  });
});

describe("Turkish locale parity", () => {
  it("matches the English locale keys", () => {
    expect(Object.keys(trTranslations).sort()).toEqual(
      Object.keys(enTranslations).sort(),
    );
  });

  it("matches the English interpolation placeholders", () => {
    const placeholderMismatches = Object.keys(enTranslations).filter(
      (key) =>
        getPlaceholders(trTranslations[key] ?? "").join("|") !==
        getPlaceholders(enTranslations[key]).join("|"),
    );

    expect(getPlaceholders(trTranslations["errors.fileTooLarge"])).toEqual([
      "{{maxSizeMB}}",
    ]);
    expect(placeholderMismatches).toEqual([]);
  });
});
