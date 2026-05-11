/**
 * Determines if a code element should be rendered as a block (with copy button)
 * or as inline code.
 *
 * A code element is considered a block if any of the following conditions are met:
 * 1. It has a language class (e.g., "language-python")
 * 2. It has the "data-language" attribute (from some markdown parsers)
 * 3. The content has multiple lines (likely a code block without language specified)
 * 4. The content looks like Python code (imports, class definitions, etc.)
 *
 * @param className - CSS class name that may contain language identifier
 * @param props - Element props that may contain data-language attribute
 * @param content - The code content to analyze
 */
export function isCodeBlock(
  className: string | undefined,
  props: Record<string, unknown> | undefined,
  content?: string,
): boolean {
  const hasLanguageClass = /language-\w+/.test(className ?? "");
  const hasDataLanguage = "data-language" in (props ?? {});

  if (hasLanguageClass || hasDataLanguage) {
    return true;
  }

  // Check if content looks like a code block
  if (content) {
    const hasMultipleLines = content.includes("\n");
    const looksLikeCode =
      /^(import |from |class |def |async def |const |let |var |function |export |interface |type )/.test(
        content.trim(),
      );

    // Multi-line content that starts with code patterns is likely a code block
    if (hasMultipleLines && looksLikeCode) {
      return true;
    }
  }

  return false;
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
