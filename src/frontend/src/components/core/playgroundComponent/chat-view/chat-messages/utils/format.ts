/**
 * Formatting utilities for chat messages.
 * Contains functions for formatting time, tool titles, and file names.
 */

/**
 * Formats a duration in milliseconds to a human-readable string.
 *
 * @param ms - Duration in milliseconds
 * @param showMsOnly - If true, only shows milliseconds (e.g., "250ms")
 * @returns Formatted time string
 *
 * @example
 * formatTime(2500, false) // "2.5s"
 * formatTime(2500, true) // "2500ms"
 * formatTime(125000, false) // "2m 5s"
 */
export function formatTime(ms: number, showMsOnly: boolean = false): string {
  if (showMsOnly) {
    return `${Math.round(ms)}ms`;
  }
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}m ${remainingSeconds.toFixed(0)}s`;
}

/**
 * Formats a duration in milliseconds to seconds with one decimal place.
 * Used for displaying "Thinking for X.Xs" or "Thought for X.Xs".
 *
 * @param ms - Duration in milliseconds
 * @returns Formatted seconds string (e.g., "2.5s", "0.5s")
 *
 * @example
 * formatSeconds(2500) // "2.5s"
 * formatSeconds(500) // "0.5s"
 * formatSeconds(1234) // "1.3s"
 */
export function formatSeconds(ms: number): string {
  const seconds = Math.ceil((ms / 1000) * 10) / 10;
  return `${seconds.toFixed(1)}s`;
}

/**
 * Formats a tool title by removing "Executed" prefix, replacing underscores with spaces,
 * removing markdown bold markers, and converting to uppercase.
 *
 * @param rawTitle - The raw title from the tool content
 * @returns Formatted tool title
 *
 * @example
 * formatToolTitle("Executed **my_tool**") // "MY TOOL"
 * formatToolTitle("some_tool_name") // "SOME TOOL NAME"
 */
export function formatToolTitle(rawTitle: string | undefined): string {
  if (!rawTitle) return "";

  return rawTitle
    .replace(/^Executed\s+/i, "")
    .replace(/_/g, " ")
    .replace(/\*\*/g, "")
    .trim()
    .toUpperCase();
}

/**
 * Formats a file name by truncating it if it exceeds the specified length,
 * while preserving the file extension.
 *
 * @param name - The file name to format
 * @param numberToTruncate - Maximum length before truncation (default: 25)
 * @returns Formatted file name
 *
 * @example
 * formatFileName("very-long-file-name.pdf", 10) // "very-long...pdf"
 * formatFileName("short.pdf", 10) // "short.pdf"
 */
export function formatFileName(
  name: string,
  numberToTruncate: number = 25,
): string {
  if (name[numberToTruncate] === undefined) {
    return name;
  }
  const fileExtension = name.split(".").pop(); // Get the file extension
  const baseName = name.slice(0, name.lastIndexOf(".")); // Get the base name without the extension
  if (baseName.length > 6) {
    return `${baseName.slice(0, numberToTruncate)}...${fileExtension}`;
  }
  return name;
}
