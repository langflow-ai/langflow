/**
 * Tests for the loadLanguage lazy-loader in i18n.ts.
 *
 * jest.setup.js mocks react-i18next globally, but this file imports the real
 * i18n instance directly — so those tests are unaffected by the global mock.
 */

// Import the real i18n instance and loadLanguage (not the mock from jest.setup.js)
jest.unmock("react-i18next");
import i18n, { loadLanguage, normalizeLanguage } from "./i18n";

describe("loadLanguage", () => {
  beforeEach(() => {
    // Clear cached non-English bundles between tests
    ["fr", "ja", "es", "de", "pt", "zh-Hans", "ko"].forEach((lang) => {
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

  it("loads and registers the Korean (ko) bundle", async () => {
    expect(i18n.hasResourceBundle("ko", "translation")).toBe(false);
    await loadLanguage("ko");
    expect(i18n.hasResourceBundle("ko", "translation")).toBe(true);
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

describe("normalizeLanguage", () => {
  it("keeps a supported language code unchanged", () => {
    expect(normalizeLanguage("ko")).toBe("ko");
    expect(normalizeLanguage("fr")).toBe("fr");
  });

  it("maps a regional Korean tag ('ko-KR') to the supported 'ko'", () => {
    expect(normalizeLanguage("ko-KR")).toBe("ko");
  });

  it("maps Chinese variants to 'zh-Hans'", () => {
    expect(normalizeLanguage("zh-CN")).toBe("zh-Hans");
    expect(normalizeLanguage("zh-Hans")).toBe("zh-Hans");
  });

  it("falls back to 'en' for empty or unsupported languages", () => {
    expect(normalizeLanguage(null)).toBe("en");
    expect(normalizeLanguage("")).toBe("en");
    expect(normalizeLanguage("xx")).toBe("en");
  });
});
