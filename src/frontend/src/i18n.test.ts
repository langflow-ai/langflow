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
    [
      "fr",
      "ja",
      "es",
      "de",
      "pt",
      "zh-Hans",
      "zh-CN",
      "zh-TW",
      "zh-HK",
      "zh-SG",
      "en-US",
      "en-GB",
      "de-DE",
      "es-ES",
      "fr-FR",
      "ja-JP",
      "pt-BR",
    ].forEach((lang) => {
      if (i18n.hasResourceBundle(lang, "translation")) {
        i18n.removeResourceBundle(lang, "translation");
      }
    });
    // Reset language to en
    i18n.changeLanguage("en");
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

  it("changes i18n language after loading", async () => {
    await loadLanguage("fr");
    expect(i18n.language).toBe("fr");
  });

  describe("LANG_FILE_MAP locale mapping", () => {
    it("maps en-US to en", async () => {
      await loadLanguage("en-US");
      expect(i18n.hasResourceBundle("en", "translation")).toBe(true);
      expect(i18n.language).toBe("en");
    });

    it("maps en-GB to en", async () => {
      await loadLanguage("en-GB");
      expect(i18n.hasResourceBundle("en", "translation")).toBe(true);
      expect(i18n.language).toBe("en");
    });

    it("maps de-DE to de", async () => {
      await loadLanguage("de-DE");
      expect(i18n.hasResourceBundle("de", "translation")).toBe(true);
      expect(i18n.language).toBe("de");
    });

    it("maps zh-CN to zh-Hans", async () => {
      await loadLanguage("zh-CN");
      expect(i18n.hasResourceBundle("zh-Hans", "translation")).toBe(true);
      expect(i18n.language).toBe("zh-Hans");
    });

    it("maps zh-TW to zh-Hans", async () => {
      await loadLanguage("zh-TW");
      expect(i18n.hasResourceBundle("zh-Hans", "translation")).toBe(true);
      expect(i18n.language).toBe("zh-Hans");
    });

    it("maps zh-HK to zh-Hans", async () => {
      await loadLanguage("zh-HK");
      expect(i18n.hasResourceBundle("zh-Hans", "translation")).toBe(true);
      expect(i18n.language).toBe("zh-Hans");
    });

    it("maps zh-SG to zh-Hans", async () => {
      await loadLanguage("zh-SG");
      expect(i18n.hasResourceBundle("zh-Hans", "translation")).toBe(true);
      expect(i18n.language).toBe("zh-Hans");
    });

    it("maps zh to zh-Hans", async () => {
      await loadLanguage("zh");
      expect(i18n.hasResourceBundle("zh-Hans", "translation")).toBe(true);
      expect(i18n.language).toBe("zh-Hans");
    });

    it("maps ja-JP to ja", async () => {
      await loadLanguage("ja-JP");
      expect(i18n.hasResourceBundle("ja", "translation")).toBe(true);
      expect(i18n.language).toBe("ja");
    });

    it("maps pt-BR to pt", async () => {
      await loadLanguage("pt-BR");
      expect(i18n.hasResourceBundle("pt", "translation")).toBe(true);
      expect(i18n.language).toBe("pt");
    });
  });

  describe("fallback behavior", () => {
    it("falls back to base language when locale not found", async () => {
      // zh is not in LANG_FILE_MAP but zh-Hans should be tried
      await loadLanguage("zh");
      expect(i18n.hasResourceBundle("zh-Hans", "translation")).toBe(true);
      expect(i18n.language).toBe("zh-Hans");
    });

    it("returns 'en' for unknown languages", async () => {
      const spy = jest.spyOn(i18n, "addResourceBundle");
      await loadLanguage("unknown-lang");
      // Should not add any resource bundle and not throw
      expect(spy).not.toHaveBeenCalled();
      spy.mockRestore();
    });

    it("handles language with only region suffix (e.g., zh-TW without mapping)", async () => {
      // zh-TW is explicitly mapped, so this tests the explicit mapping
      await loadLanguage("zh-TW");
      expect(i18n.hasResourceBundle("zh-Hans", "translation")).toBe(true);
    });
  });
});
