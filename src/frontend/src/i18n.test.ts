jest.unmock("react-i18next");

import i18n, { loadLanguage, normalizeLanguage } from "./i18n";

describe("loadLanguage", () => {
  beforeEach(() => {
    ["fr", "ja", "es", "de", "pt", "zh-Hans", "ko", "ru"].forEach((lang) => {
      if (i18n.hasResourceBundle(lang, "translation")) {
        i18n.removeResourceBundle(lang, "translation");
      }
    });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("does not call addResourceBundle for 'en' (already statically loaded)", async () => {
    const spy = jest.spyOn(i18n, "addResourceBundle");
    const loadedLanguage = await loadLanguage("en");
    expect(loadedLanguage).toBe("en");
    expect(spy).not.toHaveBeenCalled();
  });

  it("always has 'en' bundle available (statically bundled)", () => {
    expect(i18n.hasResourceBundle("en", "translation")).toBe(true);
  });

  it("loads and registers a new language bundle", async () => {
    expect(i18n.hasResourceBundle("fr", "translation")).toBe(false);
    const loadedLanguage = await loadLanguage("fr");
    expect(loadedLanguage).toBe("fr");
    expect(i18n.hasResourceBundle("fr", "translation")).toBe(true);
  });

  it("does not call addResourceBundle if language is already cached", async () => {
    await loadLanguage("fr");
    const spy = jest.spyOn(i18n, "addResourceBundle");
    await loadLanguage("fr");
    expect(spy).not.toHaveBeenCalled();
  });

  it("loads multiple different languages independently", async () => {
    await loadLanguage("fr");
    await loadLanguage("ja");
    expect(i18n.hasResourceBundle("fr", "translation")).toBe(true);
    expect(i18n.hasResourceBundle("ja", "translation")).toBe(true);
  });

  it("normalizes browser language variants without truncating zh-Hans", () => {
    expect(normalizeLanguage("zh-CN")).toBe("zh-Hans");
    expect(normalizeLanguage("zh-Hans")).toBe("zh-Hans");
    expect(normalizeLanguage("ko")).toBe("ko");
    expect(normalizeLanguage("ko-KR")).toBe("ko");
    expect(normalizeLanguage("ru")).toBe("ru");
    expect(normalizeLanguage("ru-RU")).toBe("ru");
    expect(normalizeLanguage("en-US")).toBe("en");
  });

  it("falls back to English for empty and unknown languages", () => {
    expect(normalizeLanguage("")).toBe("en");
    expect(normalizeLanguage(undefined)).toBe("en");
    expect(normalizeLanguage("zz-ZZ")).toBe("en");
  });

  it("loads zh variants through the zh-Hans bundle", async () => {
    const loadedLanguage = await loadLanguage("zh-CN");

    expect(loadedLanguage).toBe("zh-Hans");
    expect(i18n.hasResourceBundle("zh-Hans", "translation")).toBe(true);
  });

  it("loads Korean browser variants", async () => {
    const loadedLanguage = await loadLanguage("ko-KR");

    expect(loadedLanguage).toBe("ko");
    expect(i18n.hasResourceBundle("ko", "translation")).toBe(true);
  });

  it("loads Russian browser variants", async () => {
    const loadedLanguage = await loadLanguage("ru-RU");

    expect(loadedLanguage).toBe("ru");
    expect(i18n.hasResourceBundle("ru", "translation")).toBe(true);
  });

  it("falls back to English without importing missing locale files", async () => {
    const spy = jest.spyOn(i18n, "addResourceBundle");
    const loadedLanguage = await loadLanguage("zz-ZZ");

    expect(loadedLanguage).toBe("en");
    expect(spy).not.toHaveBeenCalled();
  });
});
