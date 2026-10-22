import de from "@/locales/de.json";
import en from "@/locales/en.json";
import es from "@/locales/es.json";
import fr from "@/locales/fr.json";
import ja from "@/locales/ja.json";
import ko from "@/locales/ko.json";
import pt from "@/locales/pt.json";
import zhHans from "@/locales/zh-Hans.json";
import { appendErrorSuggestion, LOGIN_ERROR_KEYS } from "../authErrorMessages";

const TRANSLATED: Record<string, Record<string, string>> = {
  de,
  es,
  fr,
  ja,
  ko,
  pt,
  "zh-Hans": zhHans,
};

describe("LOGIN_ERROR_KEYS", () => {
  // A known sign-in failure used to render its English API detail next to a
  // translated suggestion ("Incorrect username or password. Verifique…").
  it.each(Object.entries(LOGIN_ERROR_KEYS))(
    "maps %s to copy every language translates",
    (_detail, key) => {
      const english = (en as Record<string, string>)[key];
      expect(english).toBeTruthy();
      for (const strings of Object.values(TRANSLATED)) {
        expect(strings[key]).toBeTruthy();
        expect(strings[key]).not.toBe(english);
      }
    },
  );
});

describe("appendErrorSuggestion", () => {
  it("joins a detail and a suggestion into one sentence pair", () => {
    expect(appendErrorSuggestion("Wrong password", "Try again.")).toBe(
      "Wrong password. Try again.",
    );
    expect(appendErrorSuggestion("Wrong password.", "Try again.")).toBe(
      "Wrong password. Try again.",
    );
  });
});
