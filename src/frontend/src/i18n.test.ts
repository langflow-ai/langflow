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
    ["fr", "ja", "es", "de", "pt", "zh-Hans"].forEach((lang) => {
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
    const spy = jest.spyOn(i18n, "addResourceBundle");
    await loadLanguage("fr");
    expect(spy).toHaveBeenCalledWith(
      "fr",
      "translation",
      expect.any(Object),
      true,
      true,
    );
    spy.mockRestore();
  });

  it("does not call addResourceBundle if language is already cached", async () => {
    await loadLanguage("fr");
    const spy = jest.spyOn(i18n, "addResourceBundle");
    await loadLanguage("fr");
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });

  it("loads multiple different languages independently", async () => {
    const spy = jest.spyOn(i18n, "addResourceBundle");
    await loadLanguage("fr");
    await loadLanguage("ja");

    expect(spy).toHaveBeenCalledWith(
      "fr",
      "translation",
      expect.any(Object),
      true,
      true,
    );
    expect(spy).toHaveBeenCalledWith(
      "ja",
      "translation",
      expect.any(Object),
      true,
      true,
    );
    spy.mockRestore();
  });

  it("normalizes zh to the bundled zh-Hans locale", async () => {
    await loadLanguage("zh");
    expect(i18n.hasResourceBundle("zh-Hans", "translation")).toBe(true);
  });

  it("normalizes zh-CN to the bundled zh-Hans locale", async () => {
    await loadLanguage("zh-CN");
    expect(i18n.hasResourceBundle("zh-Hans", "translation")).toBe(true);
  });
});
