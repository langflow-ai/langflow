// The selector list (constants/languages.ts) and the loader list (i18n.ts) are
// separate; these fail when a language is added to one but not the other.
import { SUPPORTED_LANGUAGES } from "@/constants/languages";
import i18n, { loadLanguage } from "@/i18n";

describe("SUPPORTED_LANGUAGES", () => {
  afterEach(() => {
    localStorage.removeItem("languagePreference");
  });

  it("offers Turkish as Türkçe", () => {
    expect(SUPPORTED_LANGUAGES).toContainEqual({ code: "tr", label: "Türkçe" });
  });

  it("lists each language code once", () => {
    const codes = SUPPORTED_LANGUAGES.map((lang) => lang.code);
    expect(new Set(codes).size).toBe(codes.length);
  });

  it.each(SUPPORTED_LANGUAGES.map((lang) => lang.code))(
    "keeps %s when it is the stored preference",
    (code) => {
      localStorage.setItem("languagePreference", code);
      jest.isolateModules(() => {
        const { detectedLang } = require("@/i18n");
        expect(detectedLang).toBe(code);
      });
    },
  );

  it.each(
    SUPPORTED_LANGUAGES.map((lang) => lang.code).filter(
      (code) => code !== "en",
    ),
  )("loads a translated bundle when %s is selected", async (code) => {
    await loadLanguage(code);
    expect(i18n.hasResourceBundle(code, "translation")).toBe(true);
    expect(i18n.t("settings.saveButton", { lng: code })).not.toBe(
      i18n.t("settings.saveButton", { lng: "en" }),
    );
  });
});
