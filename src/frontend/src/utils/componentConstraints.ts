/**
 * Canonical placement policy for flow components.
 *
 * This is the single source of truth for which components may coexist in a
 * flow. Both placement paths consume the same rule engine instead of
 * re-encoding policy in different shapes:
 *   - the sidebar disables items that cannot be added (see disable-item /
 *     get-disabled-tooltip)
 *   - the canvas paste flow drops pasted nodes that cannot be placed (see
 *     flowStore `paste`)
 *
 * Adding a new constraint means editing {@link COMPONENT_CONSTRAINTS} only;
 * every placement path picks it up automatically.
 */

import { isTriggerComponent } from "./trigger-component";

// Component type identifiers referenced by name elsewhere in the UI.
export const CHAT_INPUT_COMPONENT = "ChatInput";
export const WEBHOOK_COMPONENT = "Webhook";

/**
 * Placement key every trigger node carries besides its own type. Triggers are
 * recognised by `metadata.trigger_kind`, not by type name, and wave 1 allows
 * one per flow whatever the kind. Not a valid component type name, so it can
 * never collide with one.
 */
export const TRIGGER_PLACEMENT_KEY = "@trigger";

export interface ComponentConstraint {
  /** Only one instance of this component type may exist in a flow. */
  singleton: boolean;
  /** Component types this component cannot coexist with. */
  excludes: readonly string[];
}

/** Placement policy keyed by component type. */
export const COMPONENT_CONSTRAINTS: Record<string, ComponentConstraint> = {
  [CHAT_INPUT_COMPONENT]: { singleton: true, excludes: [WEBHOOK_COMPONENT] },
  [WEBHOOK_COMPONENT]: { singleton: true, excludes: [CHAT_INPUT_COMPONENT] },
  [TRIGGER_PLACEMENT_KEY]: { singleton: true, excludes: [] },
};

export type ConstraintViolationReason = "singleton" | "exclusivity";

export interface ConstraintViolation {
  /** The component type that cannot be placed. */
  type: string;
  /** Why placement is blocked. */
  reason: ConstraintViolationReason;
  /** For "exclusivity": the already-present type it conflicts with. */
  conflictingType?: string;
}

/** Minimal shape needed to read a node's component type and trigger marker. */
type TypedNode = { data?: { type?: string; node?: unknown } };
/** Minimal shape needed to prune edges by endpoint. */
type EndpointEdge = { source: string; target: string };

/**
 * Returns the constraint for a component type, or `undefined` when the type is
 * unconstrained. Uses `Object.hasOwn` so adversarial types (e.g. "constructor")
 * cannot resolve to inherited prototype members.
 */
function getConstraint(
  type: string | undefined,
): ComponentConstraint | undefined {
  return type !== undefined && Object.hasOwn(COMPONENT_CONSTRAINTS, type)
    ? COMPONENT_CONSTRAINTS[type]
    : undefined;
}

/**
 * The placement keys a component answers to: its type, plus
 * {@link TRIGGER_PLACEMENT_KEY} when it is a trigger.
 */
export function placementKeysOf(
  type: string | undefined,
  component: unknown,
): string[] {
  const keys = type === undefined ? [] : [type];
  if (isTriggerComponent(component as Parameters<typeof isTriggerComponent>[0]))
    keys.push(TRIGGER_PLACEMENT_KEY);
  return keys;
}

const nodeKeys = (node: TypedNode) =>
  placementKeysOf(node.data?.type, node.data?.node);

/** Collects the distinct placement keys present in a set of nodes. */
export function getPresentComponentTypes(
  nodes: ReadonlyArray<TypedNode>,
): Set<string> {
  const types = new Set<string>();
  for (const node of nodes) {
    for (const key of nodeKeys(node)) types.add(key);
  }
  return types;
}

/**
 * Decides whether a single component type may be placed given the types already
 * present. Returns the violation that blocks placement, or `null` when it is
 * allowed. This is the atomic decision shared by every placement path.
 */
export function evaluatePlacement(
  candidate: string | undefined | readonly string[],
  presentTypes: ReadonlySet<string>,
): ConstraintViolation | null {
  if (Array.isArray(candidate)) {
    for (const key of candidate) {
      const violation = evaluatePlacement(key as string, presentTypes);
      if (violation) return violation;
    }
    return null;
  }
  const candidateType = candidate as string | undefined;
  const constraint = getConstraint(candidateType);
  if (!constraint || candidateType === undefined) {
    return null;
  }

  if (constraint.singleton && presentTypes.has(candidateType)) {
    return { type: candidateType, reason: "singleton" };
  }

  for (const excluded of constraint.excludes) {
    if (presentTypes.has(excluded)) {
      return {
        type: candidateType,
        reason: "exclusivity",
        conflictingType: excluded,
      };
    }
  }

  return null;
}

export interface PlaceableSelection<TNode, TEdge> {
  /** Nodes that may be placed. */
  nodes: TNode[];
  /** Edges whose endpoints both survive. */
  edges: TEdge[];
  /** Violations encountered for the nodes that were dropped. */
  violations: ConstraintViolation[];
}

/**
 * Pure filter for a paste selection: given the selection and the nodes already
 * in the flow, returns the subset that may be placed, the edges between
 * surviving nodes, and the violations encountered. Side-effect free — the
 * caller decides how to surface violations.
 *
 * Singleton and mutual-exclusivity constraints are handled in the same pass.
 * A selection that itself introduces a conflict is also resolved: the first
 * node of a constrained type wins and later conflicting nodes are dropped.
 */
export function filterPlaceableSelection<
  TNode extends { id: string; data?: { type?: string; node?: unknown } },
  TEdge extends EndpointEdge,
>(
  selection: { nodes: TNode[]; edges: TEdge[] },
  flowNodes: ReadonlyArray<TypedNode>,
): PlaceableSelection<TNode, TEdge> {
  // Fast path: nothing to enforce unless a pasted node is actually constrained.
  const hasConstrainedNode = selection.nodes.some((node) =>
    nodeKeys(node).some((key) => Boolean(getConstraint(key))),
  );
  if (!hasConstrainedNode) {
    return {
      nodes: selection.nodes,
      edges: selection.edges,
      violations: [],
    };
  }

  // Running set so a node accepted earlier in the paste constrains later ones.
  const present = getPresentComponentTypes(flowNodes);
  const removedNodeIds = new Set<string>();
  const violations: ConstraintViolation[] = [];

  const nodes = selection.nodes.filter((node) => {
    const keys = nodeKeys(node);
    const violation = evaluatePlacement(keys, present);
    if (violation) {
      violations.push(violation);
      removedNodeIds.add(node.id);
      return false;
    }
    for (const key of keys) present.add(key);
    return true;
  });

  const edges =
    removedNodeIds.size === 0
      ? selection.edges
      : selection.edges.filter(
          (edge) =>
            !removedNodeIds.has(edge.source) &&
            !removedNodeIds.has(edge.target),
        );

  return { nodes, edges, violations };
}
