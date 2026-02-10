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

/** Reserved slug for global variable references (@Vars.variable_name). */
export const VARS_SLUG = "Vars";

/** Slugs reserved by the system — never assigned to real nodes. */
export const RESERVED_SLUGS: readonly string[] = [VARS_SLUG];

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

  // biome-ignore lint/suspicious/noAssignInExpressions: standard pattern for iterating regex matches
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

/**
 * Generate a base slug from a display name for use in @references.
 *
 * Converts display names to PascalCase slugs by:
 * - Splitting on whitespace
 * - Capitalizing the first letter of each word
 * - Removing all non-alphanumeric characters
 *
 * @param displayName - The display name to convert
 * @returns A valid slug for use in @references, or "Node" if empty
 *
 * @example
 * ```ts
 * generateBaseSlug("HTTP Request") // "HTTPRequest"
 * generateBaseSlug("Chat Input") // "ChatInput"
 * generateBaseSlug("") // "Node"
 * ```
 */
export function generateBaseSlug(displayName: string): string {
  return (
    displayName
      .split(/\s+/)
      .map((word: string) => word.charAt(0).toUpperCase() + word.slice(1))
      .join("")
      .replace(/[^a-zA-Z0-9]/g, "") || "Node"
  );
}

/**
 * Return a unique slug by appending _1, _2, etc. if baseSlug already exists.
 *
 * @param baseSlug - The desired slug before deduplication
 * @param existingSlugs - Array of slugs already in use
 * @returns A slug guaranteed to not collide with existingSlugs
 */
export function deduplicateSlug(
  baseSlug: string,
  existingSlugs: string[],
): string {
  if (!existingSlugs.includes(baseSlug)) return baseSlug;
  let counter = 1;
  while (existingSlugs.includes(`${baseSlug}_${counter}`)) {
    counter++;
  }
  return `${baseSlug}_${counter}`;
}
