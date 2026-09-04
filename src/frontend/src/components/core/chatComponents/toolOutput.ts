import type { JSONValue } from "@/types/chat";

/** LangChain ToolMessage envelope shape — the readable payload lives on
 * `.content`; the rest is plumbing already exposed by the surrounding
 * accordion trigger (tool name, id, status). Used to decide whether to
 * unwrap an output object down to its `.content` field. */
export const TOOL_MESSAGE_KEYS = new Set([
  "content",
  "name",
  "id",
  "tool_call_id",
  "status",
]);

/** Detect an "envelope" tool output worth surfacing in a tabbed view:
 * a plain object with a `content` field AND at least one key OUTSIDE the
 * standard ToolMessage subset (additional_kwargs, response_metadata,
 * artifact, type, ...). Outputs that only carry standard plumbing keys
 * (name, id, tool_call_id, status) get unwrapped by `unwrapToolMessage`
 * — they don't earn a tab strip because there's nothing user-relevant
 * to hide behind it. */
export function isToolMessageEnvelope(
  output: JSONValue,
): output is Record<string, JSONValue> {
  if (output === null || typeof output !== "object" || Array.isArray(output)) {
    return false;
  }
  if (!("content" in output)) return false;
  return Object.keys(output).some((k) => !TOOL_MESSAGE_KEYS.has(k));
}

/** Strip the LangChain ToolMessage envelope from a tool output, returning
 * the inner `content` value when the keys are a subset of the canonical
 * set. Any extra key (custom tool-specific data) prevents unwrap so the
 * user doesn't silently lose information. */
export function unwrapToolMessage(output: JSONValue): JSONValue {
  if (
    output !== null &&
    typeof output === "object" &&
    !Array.isArray(output) &&
    "content" in output &&
    Object.keys(output).every((k) => TOOL_MESSAGE_KEYS.has(k))
  ) {
    return (output as Record<string, JSONValue>).content;
  }
  return output;
}

/** Detect strings that look like pre-formatted output (pandas
 * df.to_string(), ASCII tables, fixed-width logs) rather than prose or
 * markdown. Markdown rendering mangles column alignment, so these need to
 * render in a monospace <pre> block with horizontal scroll instead.
 *
 * Heuristics, any one fires:
 *  - 4+ spaces after non-space content on a line (interior column padding)
 *  - a line longer than 120 chars (long log line or wide table row)
 *  - tab characters (very rare in markdown, common in tool output)
 */
export function looksPreformatted(s: string): boolean {
  if (s.includes("\t")) return true;
  // Interior column padding (4+ spaces after non-space content on a line)
  // signals a fixed-width table or aligned output. A *leading* run of 4+
  // spaces is just a CommonMark indented code block, which should still go
  // through the markdown renderer, so require a preceding non-space char.
  if (/\S {4,}/.test(s)) return true;
  const longestLine = s.split("\n").reduce((m, l) => Math.max(m, l.length), 0);
  return longestLine > 120;
}
