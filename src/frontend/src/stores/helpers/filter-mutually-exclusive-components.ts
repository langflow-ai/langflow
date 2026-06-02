import type { Node } from "@xyflow/react";
import { MUTUALLY_EXCLUSIVE_COMPONENTS } from "@/constants/constants";
import i18n from "../../i18n";
import type { EdgeType } from "../../types/flow";
import useAlertStore from "../alertStore";

/**
 * Returns the types a component cannot coexist with, or `undefined` when the
 * type has no exclusivity rule. Uses `Object.hasOwn` so adversarial clipboard
 * types (e.g. "constructor") cannot resolve to inherited prototype members.
 */
function getConflictingTypes(
  type: string | undefined,
): readonly string[] | undefined {
  return type !== undefined &&
    Object.hasOwn(MUTUALLY_EXCLUSIVE_COMPONENTS, type)
    ? MUTUALLY_EXCLUSIVE_COMPONENTS[type]
    : undefined;
}

/**
 * Removes pasted nodes whose component type is mutually exclusive with a type
 * already present in the flow (e.g. pasting a Chat Input while a Webhook
 * exists). It also prevents a single paste selection from introducing two
 * mutually exclusive components at once. Edges referencing removed nodes are
 * dropped so the remaining selection stays consistent.
 *
 * This mirrors the sidebar's disable-item behavior so the constraint is
 * enforced for every add path, including keyboard and drop-driven paste.
 */
export function filterMutuallyExclusiveComponents(
  selection: { nodes: Node[]; edges: EdgeType[] },
  existingNodes: Node[],
): void {
  // Fast path: most pastes carry no exclusivity-constrained component, so skip
  // the full flow scan unless the selection can actually trigger a conflict.
  const hasConstrainedNode = selection.nodes.some((node) =>
    Boolean(getConflictingTypes(node.data?.type as string | undefined)),
  );
  if (!hasConstrainedNode) {
    return;
  }

  // Component types already present in the flow.
  const presentTypes = new Set<string>();
  for (const node of existingNodes) {
    const type = node.data?.type as string | undefined;
    if (type !== undefined) {
      presentTypes.add(type);
    }
  }

  const removedNodeIds = new Set<string>();

  selection.nodes = selection.nodes.filter((node) => {
    const type = node.data?.type as string | undefined;
    const conflictingTypes = getConflictingTypes(type);

    if (
      conflictingTypes?.some((conflictType) => presentTypes.has(conflictType))
    ) {
      removedNodeIds.add(node.id);
      return false;
    }

    // Track the kept type so a conflicting node later in the same paste
    // selection is dropped too.
    if (type !== undefined) {
      presentTypes.add(type);
    }
    return true;
  });

  if (removedNodeIds.size === 0) {
    return;
  }

  useAlertStore
    .getState()
    .setNoticeData({ title: i18n.t("flow.exclusiveComponentsNotPasted") });
  selection.edges = selection.edges.filter(
    (edge) =>
      !removedNodeIds.has(edge.source) && !removedNodeIds.has(edge.target),
  );
}
