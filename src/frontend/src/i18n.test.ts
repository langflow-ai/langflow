jest.unmock("react-i18next");

import { AUTO_LANGUAGE } from "./constants/languages";
import i18n, {
  getBrowserLanguage,
  loadLanguage,
  normalizeLanguage,
} from "./i18n";

const originalNavigatorLanguage = Object.getOwnPropertyDescriptor(
  window.navigator,
  "language",
);

describe("loadLanguage", () => {
  beforeEach(async () => {
    ["fr", "ja", "es", "de", "pt", "zh-Hans", "ko", "ru"].forEach((lang) => {
      if (i18n.hasResourceBundle(lang, "translation")) {
        i18n.removeResourceBundle(lang, "translation");
      }
    });
    await i18n.changeLanguage("en");
  });

  afterEach(() => {
    jest.restoreAllMocks();
    if (originalNavigatorLanguage) {
      Object.defineProperty(
        window.navigator,
        "language",
        originalNavigatorLanguage,
      );
    }
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
    expect(normalizeLanguage("zh")).toBe("zh-Hans");
    expect(normalizeLanguage("zh-CN")).toBe("zh-Hans");
    expect(normalizeLanguage("zh-Hans")).toBe("zh-Hans");
    expect(normalizeLanguage("ko")).toBe("ko");
    expect(normalizeLanguage("ko-KR")).toBe("ko");
    expect(normalizeLanguage("ru")).toBe("ru");
    expect(normalizeLanguage("ru-RU")).toBe("ru");
    expect(normalizeLanguage("en-US")).toBe("en");
  });

  it("falls back to English for Traditional Chinese browser variants", () => {
    expect(normalizeLanguage("zh-Hant")).toBe("en");
    expect(normalizeLanguage("zh-Hant-TW")).toBe("en");
    expect(normalizeLanguage("zh-TW")).toBe("en");
    expect(normalizeLanguage("zh-HK")).toBe("en");
    expect(normalizeLanguage("zh-MO")).toBe("en");
  });

  it("falls back to English for auto, empty, and unknown languages", () => {
    expect(normalizeLanguage(AUTO_LANGUAGE)).toBe("en");
    expect(normalizeLanguage("")).toBe("en");
    expect(normalizeLanguage(undefined)).toBe("en");
    expect(normalizeLanguage("zz-ZZ")).toBe("en");
  });

  it("normalizes navigator.language for automatic selection", () => {
    Object.defineProperty(window.navigator, "language", {
      configurable: true,
      value: "zh-CN",
    });

    expect(getBrowserLanguage()).toBe("zh-Hans");
  });

  it("falls back to English when navigator.language is empty", () => {
    Object.defineProperty(window.navigator, "language", {
      configurable: true,
      value: "",
    });

    expect(getBrowserLanguage()).toBe("en");
  });

  it("loads zh variants through the zh-Hans bundle and switches i18n", async () => {
    const loadedLanguage = await loadLanguage("zh-CN");

    expect(loadedLanguage).toBe("zh-Hans");
    expect(i18n.hasResourceBundle("zh-Hans", "translation")).toBe(true);
    expect(i18n.language).toBe("zh-Hans");
  });

  it("falls back to English for Traditional Chinese variants without importing missing locale files", async () => {
    const spy = jest.spyOn(i18n, "addResourceBundle");
    const loadedLanguage = await loadLanguage("zh-Hant-TW");

    expect(loadedLanguage).toBe("en");
    expect(i18n.language).toBe("en");
    expect(spy).not.toHaveBeenCalled();
  });

  it("loads Korean browser variants and switches i18n", async () => {
    const loadedLanguage = await loadLanguage("ko-KR");

    expect(loadedLanguage).toBe("ko");
    expect(i18n.hasResourceBundle("ko", "translation")).toBe(true);
    expect(i18n.language).toBe("ko");
  });

  it("loads Russian browser variants and switches i18n", async () => {
    const loadedLanguage = await loadLanguage("ru-RU");

    expect(loadedLanguage).toBe("ru");
    expect(i18n.hasResourceBundle("ru", "translation")).toBe(true);
    expect(i18n.language).toBe("ru");
  });

  it("falls back to English without importing missing locale files", async () => {
    const spy = jest.spyOn(i18n, "addResourceBundle");
    const loadedLanguage = await loadLanguage("zz-ZZ");

    expect(loadedLanguage).toBe("en");
    expect(i18n.language).toBe("en");
    expect(spy).not.toHaveBeenCalled();
  });
});
