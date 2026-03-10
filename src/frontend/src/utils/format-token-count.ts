/**
 * Formats a token count into a human-readable string.
 *
 * @param count - The number of tokens
 * @returns Formatted string (e.g., "500", "1.5K", "2.3M") or null if no valid count
 *
 * @example
 * formatTokenCount(500)     // "500"
 * formatTokenCount(1500)    // "1.5K"
 * formatTokenCount(1500000) // "1.5M"
 * formatTokenCount(null)    // null
 * formatTokenCount(0)       // null
 */
export function formatTokenCount(
  count: number | null | undefined,
): string | null {
  if (count == null || count <= 0) {
    return null;
  }

  if (count >= 1_000_000) {
    const millions = count / 1_000_000;
    return `${millions % 1 === 0 ? millions.toFixed(0) : millions.toFixed(1)}M`;
  }

  if (count >= 1_000) {
    const thousands = count / 1_000;
    return `${thousands % 1 === 0 ? thousands.toFixed(0) : thousands.toFixed(1)}K`;
  }

  return count.toString();
}
