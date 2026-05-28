/**
 * Bug 3 [P2] — Recover the actual model option from a value that has been
 * doubly-encoded somewhere in the assistant flow_update pipeline.
 *
 * The trigger reads `value?.[0]?.name` and renders it as the dropdown label.
 * A doubly-encoded payload (observed in PR-12575 OPEN BUG #3) stores the
 * entire model list as the `name` field of element 0, producing a literal
 * `[{"provider":"OpenAI","name":"gpt-4o",...]` in the trigger.
 *
 * The recovery is strictly defensive: well-formed inputs are returned
 * unchanged, so the existing renderer behaves identically for healthy
 * flows. Only when the `name` parses as a JSON array/object whose first
 * element carries `name` + `provider` do we substitute it.
 */

import type { ModelOption } from "../types";

const looksLikeJsonObjectOrArray = (s: string): boolean => {
  const trimmed = s.trim();
  return trimmed.startsWith("[") || trimmed.startsWith("{");
};

export function recoverModelOption(
  saved: ModelOption | undefined,
): ModelOption | undefined {
  if (!saved) return saved;
  if (typeof saved.name !== "string") return saved;
  if (!looksLikeJsonObjectOrArray(saved.name)) return saved;

  let parsed: unknown;
  try {
    parsed = JSON.parse(saved.name);
  } catch {
    // Name happens to start with `[`/`{` but isn't valid JSON — leave
    // it untouched so we don't silently mangle a literal model name
    // that legitimately uses those characters.
    return saved;
  }

  const candidate = Array.isArray(parsed) ? parsed[0] : parsed;
  if (
    !candidate ||
    typeof candidate !== "object" ||
    typeof (candidate as { name?: unknown }).name !== "string"
  ) {
    return saved;
  }

  const inner = candidate as Partial<ModelOption>;
  return {
    ...saved,
    name: inner.name as string,
    provider: inner.provider ?? saved.provider,
    icon: inner.icon ?? saved.icon,
    metadata: inner.metadata ?? saved.metadata,
  };
}
