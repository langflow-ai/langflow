import type { AllNodeType } from "@/types/flow";

type Translate = (key: string, options?: Record<string, unknown>) => string;

/**
 * Note nodes don't carry a meaningful component display_name (it's an empty
 * string at runtime, not undefined, so a `??` fallback to node.type never
 * triggers) — branch on the XYFlow node type instead of relying on it.
 */
export function getNodeAriaLabel(node: AllNodeType, t: Translate): string {
  if (node.type === "noteNode") {
    return t("noteNode.ariaLabel");
  }
  return t("flow.nodeAriaLabel", {
    name: node.data?.node?.display_name || node.data?.type,
  });
}

/**
 * Accessible names for a whole canvas, aligned by index with `nodes`.
 *
 * Canvas nodes expose `role="application"`, so every one of them needs a
 * unique accessible name (IBM Equal Access `aria_application_label_unique`,
 * WCAG 4.1.2). A flow with two nodes of the same component type would
 * otherwise share one name. Only colliding labels get a trailing ordinal
 * ("Chat Input node 1" / "Chat Input node 2"); a node whose label is already
 * unique keeps it verbatim. Ordinals follow the order of `nodes`, so the same
 * list always produces the same names.
 */
export function getNodeAriaLabels(
  nodes: AllNodeType[],
  t: Translate,
): string[] {
  const labels = nodes.map((node) => getNodeAriaLabel(node, t));

  const totals = new Map<string, number>();
  for (const label of labels) {
    totals.set(label, (totals.get(label) ?? 0) + 1);
  }

  const assigned = new Map<string, number>();
  return labels.map((label) => {
    if ((totals.get(label) ?? 0) < 2) return label;
    const ordinal = (assigned.get(label) ?? 0) + 1;
    assigned.set(label, ordinal);
    return t("flow.nodeAriaLabelOrdinal", { label, ordinal });
  });
}
