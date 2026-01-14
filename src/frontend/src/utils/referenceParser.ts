import type { ParsedReference } from "@/types/references";

/**
 * Regular expression pattern for matching inline variable references.
 *
 * Pattern breakdown:
 * - `(?<!\w)` - Negative lookbehind: @ must not be preceded by word char (prevents email matches like user@domain.com)
 * - `@(\w+)` - @ followed by node slug (captured in group 1)
 * - `\.(\w+)` - Dot followed by output name (captured in group 2)
 * - `((?:\.\w+|\[\d+\])*)` - Optional dot paths and array indices (captured in group 3)
 *
 * @example
 * - `@ChatInput.message` - Simple reference
 * - `@API.data.user.name` - Reference with dot path
 * - `@List.items[0]` - Reference with array index
 */
export const REFERENCE_PATTERN = /(?<!\w)@(\w+)\.(\w+)((?:\.\w+|\[\d+\])*)/g;

/**
 * Parse all @references from a text string.
 *
 * @param text - The text to parse for references
 * @returns Array of parsed references with node slug, output name, optional dot path, and position info
 *
 * @example
 * ```ts
 * const refs = parseReferences("Hello @ChatInput.message, your balance is @Account.balance");
 * // Returns:
 * // [
 * //   { nodeSlug: "ChatInput", outputName: "message", fullPath: "@ChatInput.message", ... },
 * //   { nodeSlug: "Account", outputName: "balance", fullPath: "@Account.balance", ... }
 * // ]
 * ```
 */
export function parseReferences(text: string): ParsedReference[] {
  const references: ParsedReference[] = [];
  let match: RegExpExecArray | null;

  // Reset lastIndex for global regex
  REFERENCE_PATTERN.lastIndex = 0;

  while ((match = REFERENCE_PATTERN.exec(text)) !== null) {
    const nodeSlug = match[1];
    const outputName = match[2];
    const dotPathRaw = match[3];
    const fullPath = match[0];

    // Remove leading dot if present, but keep leading bracket for array access
    let dotPath: string | undefined;
    if (dotPathRaw) {
      dotPath = dotPathRaw.startsWith(".") ? dotPathRaw.slice(1) : dotPathRaw;
    }

    references.push({
      nodeSlug,
      outputName,
      dotPath,
      fullPath,
      startIndex: match.index,
      endIndex: match.index + fullPath.length,
    });
  }

  return references;
}
