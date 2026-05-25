/**
 * Determines if a code element should be rendered as a block (with copy button)
 * or as inline code.
 *
 * A code element is considered a block if any of the following is true:
 * 1. It has a language class (e.g., "language-python") — explicit fenced block
 *    with a language hint, e.g. ```python ... ```
 * 2. It has a non-empty `data-language` attribute — same idea, just supplied
 *    via attribute instead of class
 * 3. It has a `data-language` attribute (even empty) AND the content spans
 *    multiple lines — fenced block without a language hint, but the multi-line
 *    content makes it unambiguously a code block
 *
 * It is **inline** otherwise. In particular, a fenced block whose content is a
 * single short line and carries no language hint (`` ``` ` `` ``url`` `` ``` ``)
 * is treated as inline. LLMs frequently emit those for short values like URLs,
 * numeric expressions, or single-word labels; rendering each one as a full
 * code-panel breaks the surrounding paragraph/list flow.
 *
 * @param className - CSS class name that may contain a language identifier
 * @param props - Element props that may contain a `data-language` attribute
 * @param content - The code content to analyze
 */
export function isCodeBlock(
  className: string | undefined,
  props: Record<string, unknown> | undefined,
  content?: string,
): boolean {
  const hasLanguageClass = /language-\w+/.test(className ?? "");
  if (hasLanguageClass) {
    return true;
  }

  const safeProps = props ?? {};
  const hasDataLanguageAttr = "data-language" in safeProps;
  if (!hasDataLanguageAttr) {
    return false;
  }

  const dataLanguage = safeProps["data-language"];
  const hasNonEmptyLanguage =
    typeof dataLanguage === "string" && dataLanguage.length > 0;
  if (hasNonEmptyLanguage) {
    return true;
  }

  // `data-language=""` — fenced block without a language hint. Block-render
  // only when the content spans multiple lines; otherwise treat as inline so a
  // short LLM-emitted ```URL``` or ```923 * 31233``` doesn't break the
  // surrounding text flow.
  return typeof content === "string" && content.includes("\n");
}

/**
 * Extracts the language identifier from a className or detects from content.
 * Returns empty string if no language is found.
 */
export function extractLanguage(
  className: string | undefined,
  content?: string,
): string {
  const match = /language-(\w+)/.exec(className ?? "");
  if (match?.[1]) {
    return match[1];
  }

  // Try to detect language from content
  if (content) {
    const trimmed = content.trim();
    // Python patterns
    if (
      /^(from |import |class \w+.*:|def \w+|async def )/.test(trimmed) ||
      trimmed.includes("self.") ||
      trimmed.includes("__init__")
    ) {
      return "python";
    }
    // JavaScript/TypeScript patterns
    if (
      /^(const |let |var |function |export |import \{|interface |type )/.test(
        trimmed,
      )
    ) {
      return "javascript";
    }
  }

  return "";
}
