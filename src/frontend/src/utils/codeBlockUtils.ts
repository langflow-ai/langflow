/**
 * Determines if a code element should be rendered as a block (with copy button)
 * or as inline code.
 *
 * A code element is considered a block if any of the following conditions are met:
 * 1. It has a language class (e.g., "language-python")
 * 2. It has the "data-language" attribute (from some markdown parsers)
 * 3. The content contains newlines (multi-line code)
 */
export function isCodeBlock(
  className: string | undefined,
  props: Record<string, unknown> | undefined,
  content: string,
): boolean {
  const languageMatch = /language-(\w+)/.exec(className ?? "");
  const hasLanguageClass = !!languageMatch;
  const hasDataLanguage = "data-language" in (props ?? {});
  const hasNewlines = content.includes("\n");

  return hasLanguageClass || hasDataLanguage || hasNewlines;
}

/**
 * Extracts the language identifier from a className.
 * Returns empty string if no language is found.
 */
export function extractLanguage(className: string | undefined): string {
  const match = /language-(\w+)/.exec(className ?? "");
  return match?.[1] ?? "";
}
