/**
 * Guards the shipped locale bundles against silent English leakage.
 *
 * `i18n.ts` sets `fallbackLng: "en"`, so a key missing from a locale never
 * surfaces as a raw key — it renders the English string inside an otherwise
 * translated screen, which is invisible to every other test we run.
 */
import de from "../de.json";
import en from "../en.json";
import es from "../es.json";
import fr from "../fr.json";
import ja from "../ja.json";
import pt from "../pt.json";
import zhHans from "../zh-Hans.json";

const LOCALES: Record<string, Record<string, string>> = {
  de,
  es,
  fr,
  ja,
  pt,
  "zh-Hans": zhHans,
};

const englishKeys = Object.keys(en as Record<string, string>);

/** `{{name}}` placeholders i18next substitutes at render time. */
const placeholders = (value: string): string[] =>
  (value.match(/\{\{\s*[\w.]+\s*\}\}/g) ?? [])
    .map((match) => match.replace(/[{}\s]/g, ""))
    .sort();

describe("locale bundles", () => {
  it.each(Object.keys(LOCALES))(
    "%s translates every key English ships",
    (locale) => {
      const missing = englishKeys.filter((key) => !(key in LOCALES[locale]));

      expect(missing).toEqual([]);
    },
  );

  // A dropped or renamed placeholder renders the literal `{{provider}}` to the
  // user, so parity of the key set alone is not enough.
  it.each(Object.keys(LOCALES))(
    "%s keeps the interpolation placeholders of each string",
    (locale) => {
      const mismatched = englishKeys
        .filter((key) => key in LOCALES[locale])
        .map((key) => ({
          key,
          english: placeholders((en as Record<string, string>)[key]),
          translated: placeholders(LOCALES[locale][key]),
        }))
        .filter(
          ({ english, translated }) =>
            english.join("|") !== translated.join("|"),
        )
        .map(({ key }) => key);

      expect(mismatched).toEqual([]);
    },
  );
});
