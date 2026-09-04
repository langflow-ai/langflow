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
    ["fr", "ja", "es", "de", "pt", "ru", "zh-Hans"].forEach((lang) => {
      if (i18n.hasResourceBundle(lang, "translation")) {
        i18n.removeResourceBundle(lang, "translation");
      }
    });
  });

  afterEach(async () => {
    await i18n.changeLanguage("en");
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

  it("loads and registers the Russian language bundle", async () => {
    expect(i18n.hasResourceBundle("ru", "translation")).toBe(false);
    await loadLanguage("ru");
    expect(i18n.hasResourceBundle("ru", "translation")).toBe(true);
  });

  it("uses Russian plural forms", async () => {
    await loadLanguage("ru");
    await i18n.changeLanguage("ru");

    expect(i18n.t("chat.deleteSessionsCount", { count: 1 })).toBe(
      "Удалить 1 сессию",
    );
    expect(i18n.t("chat.deleteSessionsCount", { count: 2 })).toBe(
      "Удалить 2 сессии",
    );
    expect(i18n.t("chat.deleteSessionsCount", { count: 5 })).toBe(
      "Удалить 5 сессий",
    );
    expect(i18n.t("mainPage.timeElapsed.year", { count: 1 })).toBe("1 год");
    expect(i18n.t("mainPage.timeElapsed.year", { count: 2 })).toBe("2 года");
    expect(i18n.t("mainPage.timeElapsed.year", { count: 5 })).toBe("5 лет");
    expect(i18n.t("mcp.toolCount", { count: 1 })).toBe("1 инструмент");
    expect(i18n.t("mcp.toolCount", { count: 2 })).toBe("2 инструмента");
    expect(i18n.t("mcp.toolCount", { count: 5 })).toBe("5 инструментов");
    expect(i18n.t("agentTab.turns", { count: 1 })).toBe("1 запрос");
    expect(i18n.t("agentTab.turns", { count: 2 })).toBe("2 запроса");
    expect(i18n.t("agentTab.turns", { count: 5 })).toBe("5 запросов");
    expect(i18n.t("deployments.flow", { count: 1 })).toBe("поток");
    expect(i18n.t("deployments.flow", { count: 2 })).toBe("потока");
    expect(i18n.t("deployments.flow", { count: 5 })).toBe("потоков");
    expect(i18n.t("knowledge.fileCount", { count: 1 })).toBe("1 файл");
    expect(i18n.t("knowledge.fileCount", { count: 2 })).toBe("2 файла");
    expect(i18n.t("knowledge.fileCount", { count: 5 })).toBe("5 файлов");
    expect(i18n.t("knowledge.charCount", { count: 21 })).toBe("21 символ");
    expect(i18n.t("knowledge.charCount", { count: 22 })).toBe("22 символа");
    expect(i18n.t("knowledge.charCount", { count: 25 })).toBe("25 символов");
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
