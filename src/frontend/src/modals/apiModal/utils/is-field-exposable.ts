import type { AllNodeType, EdgeType } from "@/types/flow";
import { scapeJSONParse } from "@/utils/reactflowUtils";

/**
 * Single exposure predicate (LE-1810): a field is only advertised as an API
 * input when ALL preconditions hold. `api_editable` is never mutated on the
 * real flow — a field that fails a precondition simply stops being derived
 * into the tweaks/snippets until the precondition holds again.
 *
 * Preconditions:
 * - `api_editable === true` — the user exposed it in the parameters panel;
 * - on the node (`advanced !== true`) — an off-node field is not callable,
 *   so it cannot be exposed (exposure is coupled to being on the node);
 * - not edge-connected — a connected input is driven by the edge at runtime;
 * - not disabled by active tool mode — same "disabled fields can't be called
 *   via the API" rule the panel row enforces;
 * - not the code field nor an internal (`_`-prefixed) field.
 */
export const isFieldExposable = (
  node: AllNodeType,
  name: string,
  edges: EdgeType[],
): boolean => {
  const template = node.data?.node?.template?.[name];
  if (!template) return false;
  if (template.api_editable !== true) return false;
  if (template.advanced === true) return false;
  if ((node.data?.node?.tool_mode ?? false) && (template.tool_mode ?? false)) {
    return false;
  }
  if (name === "code" || name.startsWith("_")) return false;
  return !edges.some(
    (edge) =>
      edge.target === node.id &&
      edge.targetHandle &&
      scapeJSONParse(edge.targetHandle)?.fieldName === name,
  );
};
