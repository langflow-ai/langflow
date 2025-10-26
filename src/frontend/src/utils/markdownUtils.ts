/**
 * Utility functions for processing markdown content, particularly tables
 */

/**
 * Detects if the given text contains a markdown table
 */
export const isMarkdownTable = (text: string): boolean => {
  if (!text?.trim()) return false;

  // Single regex to detect markdown table with header separator
  return /\|.*\|.*\n\s*\|[\s\-:]+\|/m.test(text);
};

/**
 * Removes completely empty rows from markdown tables
 */
export const cleanupTableEmptyCells = (text: string): string => {
  return text
    .split("\n")
    .filter((line) => {
      const trimmed = line.trim();

      // Keep non-table lines
      if (!trimmed.includes("|")) return true;

      // Keep separator rows (contain only |, -, :, spaces)
      if (/^\|[\s\-:]+\|$/.test(trimmed)) return true;

      // For data rows, check if any cell has content
      const cells = trimmed.split("|").slice(1, -1); // Remove delimiter cells
      return cells.some((cell) => cell.trim() !== "");
    })
    .join("\n");
};

/**
 * Preprocesses chat messages by handling <think> tags and cleaning up tables
 */
export const preprocessChatMessage = (text: string): string => {
  // Handle <think> tags
  let processed = text
    .replace(/<think>/g, "`<think>`")
    .replace(/<\/think>/g, "`</think>`");

  // Clean up tables if present
  if (isMarkdownTable(processed)) {
    processed = cleanupTableEmptyCells(processed);
  }

  return processed;
};

/**
 * Detects if text contains Markdown formatting patterns
 * Returns true if any Markdown syntax is found, false for plain text
 *
 * @param text - Text to analyze
 * @returns boolean indicating if Markdown formatting is present
 *
 * @example
 * hasMarkdownFormatting("### Title")  // true
 * hasMarkdownFormatting("plain text") // false
 */
export const hasMarkdownFormatting = (text: string): boolean => {
  if (!text || text.trim().length === 0) return false;

  const markdownPatterns = [
    /^#{1,6}\s+/m,              // Headings: # ## ###
    /\*\*[^*]+\*\*/,            // Bold: **text**
    /__[^_]+__/,                // Bold: __text__
    /^[-*+]\s+/m,               // Unordered lists: - * +
    /^\d+\.\s+/m,               // Ordered lists: 1. 2.
    /```[\s\S]*?```/,           // Code blocks: ```code```
    /`[^`]+`/,                  // Inline code: `code`
    /\[.+?\]\(.+?\)/,           // Links: [text](url)
    /^>\s+/m,                   // Blockquotes: > quote
    /^\|.+\|$/m,                // Tables: | col | col |
  ];

  return markdownPatterns.some(pattern => pattern.test(text));
};
