/**
 * Prompt variable naming rules shared by every place that highlights or lists them.
 *
 * Mirror of `RESERVED_VARIABLE_PREFIX` / `_check_reserved_prefix` in
 * `src/lfx/src/lfx/base/prompts/api_utils.py`. Keys prefixed with an underscore are
 * node-template metadata (`_type`, `_frontend_node_flow_id`, ...), not component fields,
 * so a variable in that namespace can never be rendered as an input or a handle. The
 * backend rejects the name on Check & Save; these helpers let the editor say so while the
 * user is still typing.
 *
 * The case list is mirrored by `test_validate_prompt_reserved_prefix.py`; keep the two in
 * sync when the rule changes.
 */
export const RESERVED_VARIABLE_PREFIX = "_";

export function isReservedVariableName(name: string): boolean {
  return name.startsWith(RESERVED_VARIABLE_PREFIX);
}

/** Class applied to a highlighted variable, red when the name will be rejected. */
export function variableHighlightClass(name: string): string {
  return isReservedVariableName(name)
    ? "chat-message-highlight-invalid"
    : "chat-message-highlight";
}
