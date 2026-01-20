export type ParsedStreamingContent = {
  preCodeText: string;
  code: string | null;
  isCodeComplete: boolean;
};

/**
 * Parses streaming content to separate pre-code text from code blocks.
 */
export function parseStreamingContent(text: string): ParsedStreamingContent {
  const codeBlockMatch = text.match(/```(?:python)?\n?/);

  if (!codeBlockMatch) {
    return {
      preCodeText: text,
      code: null,
      isCodeComplete: false,
    };
  }

  const codeStartIndex = codeBlockMatch.index!;
  const preCodeText = text.slice(0, codeStartIndex).trim();
  const afterCodeStart = text.slice(codeStartIndex + codeBlockMatch[0].length);

  const closingIndex = afterCodeStart.indexOf("```");

  if (closingIndex === -1) {
    return {
      preCodeText,
      code: afterCodeStart,
      isCodeComplete: false,
    };
  }

  return {
    preCodeText,
    code: afterCodeStart.slice(0, closingIndex),
    isCodeComplete: true,
  };
}

/**
 * Extracts pre-code explanation text from streaming content.
 * Returns the text before any code block (```python or ```).
 */
export function extractPreCodeText(streamingText: string): string {
  if (!streamingText) {
    return "";
  }

  return parseStreamingContent(streamingText).preCodeText;
}
