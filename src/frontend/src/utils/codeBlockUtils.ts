/**
 * Determines if a code element should be rendered as a block (with copy button)
 * or as inline code.
 *
 * A code element is considered a block if any of the following conditions are met:
 * 1. It has a language class (e.g., "language-python")
 * 2. It has the "data-language" attribute (from some markdown parsers)
 *
 * Note: We intentionally do NOT use newlines as a criterion for detecting code blocks.
 * During streaming, react-markdown may create multiple code elements for a single
 * code block, and using newlines would cause each fragment to be rendered as a
 * separate block, resulting in duplicated/broken code block rendering.
 *
 * @param className - CSS class name that may contain language identifier
 * @param props - Element props that may contain data-language attribute
 * @param _content - Unused. Kept for backward compatibility with existing call sites.
 */
export function isCodeBlock(
  className: string | undefined,
  props: Record<string, unknown> | undefined,
  _content?: string,
): boolean {
  const hasLanguageClass = /language-\w+/.test(className ?? "");
  const hasDataLanguage = "data-language" in (props ?? {});

  return hasLanguageClass || hasDataLanguage;
}

/**
 * Extracts the language identifier from a className.
 * Returns empty string if no language is found.
 */
export function extractLanguage(className: string | undefined): string {
  const match = /language-(\w+)/.exec(className ?? "");
  return match?.[1] ?? "";
}
