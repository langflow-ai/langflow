/**
 * Tests for the loadLanguage lazy-loader in i18n.ts.
 *
 * jest.setup.js mocks react-i18next globally, but this file imports the real
 * i18n instance directly — so those tests are unaffected by the global mock.
 */

// Import the real i18n instance and loadLanguage (not the mock from jest.setup.js)
jest.unmock("react-i18next");

import i18n, { loadLanguage } from "./i18n";

describe("loadLanguage", () => {
  beforeEach(() => {
    // Clear cached non-English bundles between tests
    ["fr", "ja", "ko", "es", "de", "pt", "tr", "zh-Hans"].forEach((lang) => {
      if (i18n.hasResourceBundle(lang, "translation")) {
        i18n.removeResourceBundle(lang, "translation");
      }
    });
  });

  it("does not call addResourceBundle for 'en' (already statically loaded)", async () => {
    const spy = jest.spyOn(i18n, "addResourceBundle");
    await loadLanguage("en");
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });

  it("always has 'en' bundle available (statically bundled)", () => {
    expect(i18n.hasResourceBundle("en", "translation")).toBe(true);
  });

  it("loads and registers a new language bundle", async () => {
    expect(i18n.hasResourceBundle("fr", "translation")).toBe(false);
    await loadLanguage("fr");
    expect(i18n.hasResourceBundle("fr", "translation")).toBe(true);
  });

  it("does not call addResourceBundle if language is already cached", async () => {
    await loadLanguage("fr");
    const spy = jest.spyOn(i18n, "addResourceBundle");
    await loadLanguage("fr");
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });

  it("loads multiple different languages independently", async () => {
    await loadLanguage("fr");
    await loadLanguage("ja");
    expect(i18n.hasResourceBundle("fr", "translation")).toBe(true);
    expect(i18n.hasResourceBundle("ja", "translation")).toBe(true);
  });
});

describe("Turkish locale", () => {
  afterEach(() => {
    localStorage.removeItem("languagePreference");
  });

  it("loads the Turkish bundle with translated strings", async () => {
    await loadLanguage("tr");

    expect(i18n.hasResourceBundle("tr", "translation")).toBe(true);
    expect(i18n.t("settings.saveButton", { lng: "tr" })).toBe("Kaydet");
  });

  // detectedLang is computed once at import, so each case loads a fresh module.
  it.each([
    ["tr", "tr"],
    ["tr-TR", "tr"],
    ["tr-CY", "tr"],
    ["trk", "en"],
  ])(
    "maps a stored preference of %s to %s and sets <html lang>",
    (stored, expected) => {
      localStorage.setItem("languagePreference", stored);

      jest.isolateModules(() => {
        const { detectedLang } = require("./i18n");
        expect(detectedLang).toBe(expected);
      });
      expect(document.documentElement.lang).toBe(expected);
    },
  );
});
