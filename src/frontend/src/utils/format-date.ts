import i18n from "@/i18n";

/**
 * The language the UI is rendered in, as a BCP 47 tag for `Intl`.
 *
 * Dates shown next to translated labels have to follow the language the user
 * picked, not the one the code was written in: `8/27, 4:45:21 PM` reads as a
 * different date to a reader of `27/08, 16:45:21`, and a hardcoded `"en-US"`
 * gives every non-English locale the American reading.
 *
 * Returns `undefined` when i18n has not resolved a language yet, which makes
 * `Intl` fall back to the browser's locale rather than to a language nobody
 * chose.
 */
export function uiLocale(): string | undefined {
  return i18n.language || undefined;
}
