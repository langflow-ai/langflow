import type { APITemplateType, InputFieldType } from "@/types/api";
import type { AllNodeType, EdgeType } from "@/types/flow";

/**
 * Describing a graph difference in words people can act on.
 *
 * The sentences are generated from the diff, never by a model: someone is waiting
 * mid-conflict, so this has to be instant, offline, and identical on two machines
 * for the same change. Long values defeat an inline "a → b", so every field change
 * also carries the raw before/after for the dialog to show on demand.
 */

export type ChangeBadge = "added" | "removed" | "modified";

export type ChangeSentence = {
  key: string;
  params: Record<string, string>;
};

export type FlowChange = {
  id: string;
  /** Component-level identity. Two changes sharing it cannot both be applied. */
  targetKey: string;
  /** What `targetId` names. Kept as fields because a Langflow edge id contains ":". */
  targetKind: "node" | "edge";
  targetId: string;
  badge: ChangeBadge;
  label: string;
  /** The component the change belongs to, which is what the reader chooses. */
  owner: string;
  sentence: ChangeSentence;
  detail?: { before: string; after: string };
};

/** Every change to one component, as the dialog offers it: together or not at all. */
export type ChangeGroup = {
  targetKey: string;
  targetKind: "node" | "edge";
  targetId: string;
  label: string;
  badge: ChangeBadge;
  changes: FlowChange[];
};

type Graph = {
  nodes?: AllNodeType[] | null;
  edges?: EdgeType[] | null;
} | null;

const INLINE_VALUE_LIMIT = 60;

/** Stands in for an absent value, so a sentence never reads "updated from  to x". */
const EMPTY_VALUE = "—";

const nodeList = (graph: Graph): AllNodeType[] => graph?.nodes ?? [];
const edgeList = (graph: Graph): EdgeType[] => graph?.edges ?? [];

const byId = <T extends { id: string }>(items: T[]): Map<string, T> =>
  new Map(items.map((item) => [item.id, item]));

type NodeInner = {
  display_name?: string;
  name?: string;
  template?: APITemplateType;
};

const nodeInner = (node: AllNodeType | undefined): NodeInner =>
  (node?.data?.node as NodeInner | undefined) ?? {};

export const changeOwnerName = (node: AllNodeType | undefined): string => {
  const inner = nodeInner(node);
  return inner.display_name || inner.name || node?.id || "Component";
};

const nodeTemplate = (node: AllNodeType | undefined): APITemplateType =>
  nodeInner(node).template ?? {};

const isSecretEntry = (entry: InputFieldType | undefined): boolean =>
  entry?.password === true || entry?.type === "SecretStr";

const fieldLabel = (entry: InputFieldType | undefined, name: string): string =>
  entry?.display_name || name;

/** Key order is not a change, so objects are sorted before comparison. Arrays keep theirs. */
const sortDeep = (value: unknown): unknown => {
  if (Array.isArray(value)) return value.map(sortDeep);
  if (value === null || typeof value !== "object") return value;
  return Object.fromEntries(
    Object.keys(value as Record<string, unknown>)
      .sort()
      .map((key) => [key, sortDeep((value as Record<string, unknown>)[key])]),
  );
};

/** A list of named things reads as its names, not as the objects carrying them. */
const namedList = (value: unknown): string | null => {
  if (!Array.isArray(value)) return null;
  if (value.length === 0) return "[]";
  const names = value.map((item) =>
    item !== null && typeof item === "object" && "name" in item
      ? String((item as { name: unknown }).name)
      : null,
  );
  return names.every((name) => name !== null) ? names.join(", ") : null;
};

/** Stable text for comparison and for the raw-diff view. */
export const renderValue = (value: unknown): string => {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  // A model selection is a list of objects carrying icons, providers and metadata.
  // Serialised whole it filled the dialog with twenty lines of JSON to say the model
  // changed, and the name — the only part a reader wants — was buried in it.
  const named = namedList(value);
  if (named !== null) return named;
  try {
    // Not JSON.stringify's replacer-array form: on an array that argument is read
    // as a key allow-list of indices, which erased every field inside it — so two
    // different model selections both rendered as "[{}]" and compared equal.
    return JSON.stringify(sortDeep(value), null, 2);
  } catch {
    return String(value);
  }
};

const isShort = (before: string, after: string): boolean =>
  before.length <= INLINE_VALUE_LIMIT &&
  after.length <= INLINE_VALUE_LIMIT &&
  !before.includes("\n") &&
  !after.includes("\n");

const edgeEndpoints = (
  edge: EdgeType,
  nodes: Map<string, AllNodeType>,
): { source: string; target: string } => ({
  source: changeOwnerName(nodes.get(edge.source)),
  target: changeOwnerName(nodes.get(edge.target)),
});

const movedOnCanvas = (base: AllNodeType, next: AllNodeType): boolean =>
  Math.round(base.position?.x ?? 0) !== Math.round(next.position?.x ?? 0) ||
  Math.round(base.position?.y ?? 0) !== Math.round(next.position?.y ?? 0);

const diffNodeFields = (
  base: AllNodeType,
  next: AllNodeType,
  changes: FlowChange[],
): void => {
  // Layout is work too. Leaving it out told people who had only rearranged the
  // canvas that they had no changes, right as they were deciding what to keep.
  if (movedOnCanvas(base, next)) {
    changes.push({
      id: `node:${next.id}:position`,
      targetKey: `node:${next.id}`,
      targetKind: "node",
      targetId: next.id,
      badge: "modified",
      label: changeOwnerName(next),
      owner: changeOwnerName(next),
      sentence: { key: "multiEdit.change.nodeMoved", params: {} },
    });
  }

  const baseTemplate = nodeTemplate(base);
  const nextTemplate = nodeTemplate(next);
  // Underscore-prefixed keys are node-template metadata (`_type`,
  // `_frontend_node_flow_id`, ...), not component fields. The rest of the editor
  // filters them out of every render path; listing them here offered the reader
  // "_frontend_node_flow_id updated from c1cb7b3c to 64c4789a" as their own work.
  const names = new Set(
    [...Object.keys(baseTemplate), ...Object.keys(nextTemplate)].filter(
      (name) => !name.startsWith("_"),
    ),
  );

  for (const name of names) {
    const baseEntry = baseTemplate[name];
    const nextEntry = nextTemplate[name];
    const before = renderValue(baseEntry?.value);
    const after = renderValue(nextEntry?.value);
    if (before === after) continue;

    const secret = isSecretEntry(nextEntry) || isSecretEntry(baseEntry);
    const label = fieldLabel(nextEntry ?? baseEntry, name);
    const owner = changeOwnerName(next);
    const short = !secret && isShort(before, after);

    changes.push({
      id: `node:${next.id}:field:${name}`,
      targetKey: `node:${next.id}`,
      targetKind: "node",
      targetId: next.id,
      badge: "modified",
      label,
      owner,
      sentence: short
        ? {
            key: "multiEdit.change.fieldShort",
            params: {
              field: label,
              before: before || EMPTY_VALUE,
              after: after || EMPTY_VALUE,
            },
          }
        : {
            key: "multiEdit.change.fieldLong",
            params: { field: label },
          },
      // A secret's value must not reach the sentence or the raw view.
      detail: secret ? undefined : { before, after },
    });
  }
};

/** Changes that turn *base* into *next*, one entry per thing a person would recognise. */
export const diffGraphs = (base: Graph, next: Graph): FlowChange[] => {
  const changes: FlowChange[] = [];
  const baseNodes = byId(nodeList(base));
  const nextNodes = byId(nodeList(next));

  for (const [id, node] of nextNodes) {
    if (!baseNodes.has(id)) {
      changes.push({
        id: `node:${id}:added`,
        targetKey: `node:${id}`,
        targetKind: "node",
        targetId: id,
        badge: "added",
        label: changeOwnerName(node),
        owner: changeOwnerName(node),
        sentence: { key: "multiEdit.change.nodeAdded", params: {} },
      });
    }
  }

  for (const [id, node] of baseNodes) {
    if (!nextNodes.has(id)) {
      changes.push({
        id: `node:${id}:removed`,
        targetKey: `node:${id}`,
        targetKind: "node",
        targetId: id,
        badge: "removed",
        label: changeOwnerName(node),
        owner: changeOwnerName(node),
        sentence: { key: "multiEdit.change.nodeRemoved", params: {} },
      });
    }
  }

  for (const [id, node] of nextNodes) {
    const previous = baseNodes.get(id);
    if (previous) diffNodeFields(previous, node, changes);
  }

  const baseEdges = byId(edgeList(base));
  const nextEdges = byId(edgeList(next));
  const allNodes = new Map([...baseNodes, ...nextNodes]);

  for (const [id, edge] of nextEdges) {
    if (baseEdges.has(id)) continue;
    const { source, target } = edgeEndpoints(edge, allNodes);
    changes.push({
      id: `edge:${id}:added`,
      targetKey: `edge:${id}`,
      targetKind: "edge",
      targetId: id,
      badge: "added",
      label: `${source} → ${target}`,
      owner: `${source} → ${target}`,
      sentence: {
        key: "multiEdit.change.edgeAdded",
        params: { source, target },
      },
    });
  }

  for (const [id, edge] of baseEdges) {
    if (nextEdges.has(id)) continue;
    const { source, target } = edgeEndpoints(edge, allNodes);
    changes.push({
      id: `edge:${id}:removed`,
      targetKey: `edge:${id}`,
      targetKind: "edge",
      targetId: id,
      badge: "removed",
      label: `${source} → ${target}`,
      owner: `${source} → ${target}`,
      sentence: {
        key: "multiEdit.change.edgeRemoved",
        params: { source, target },
      },
    });
  }

  return changes;
};

/**
 * One row per component, because that is the unit of the decision.
 *
 * Listing every change separately gave a moved node and an edited field of the
 * same component two checkboxes that always moved together, which promises a
 * choice the merge cannot honour. The strongest badge wins the header: a component
 * that was added and then edited reads as added.
 */
export const groupChangesByTarget = (changes: FlowChange[]): ChangeGroup[] => {
  const groups = new Map<string, ChangeGroup>();
  for (const change of changes) {
    const existing = groups.get(change.targetKey);
    if (!existing) {
      groups.set(change.targetKey, {
        targetKey: change.targetKey,
        targetKind: change.targetKind,
        targetId: change.targetId,
        label: change.owner,
        badge: change.badge,
        changes: [change],
      });
      continue;
    }
    existing.changes.push(change);
    if (change.badge !== "modified") existing.badge = change.badge;
  }
  return [...groups.values()];
};

/**
 * Every change that travels with *change*, because taking one takes the component.
 *
 * Selection has to be grouped this way or the dialog lies: applying a change replaces
 * the whole component, so ticking one of their two edits to it would silently bring
 * the other along.
 */
export const siblingChangeIds = (
  changes: FlowChange[],
  targetKey: string,
): string[] =>
  changes
    .filter((change) => change.targetKey === targetKey)
    .map((change) => change.id);

/** Apply the selected subset of *theirChanges* on top of *mine*, taken from *theirGraph*. */
export const applySelectedChanges = (
  mine: Graph,
  theirGraph: Graph,
  changes: FlowChange[],
  selectedIds: Set<string>,
): { nodes: AllNodeType[]; edges: EdgeType[] } => {
  const nodes = byId(nodeList(mine));
  const edges = byId(edgeList(mine));
  const theirNodes = byId(nodeList(theirGraph));
  const theirEdges = byId(edgeList(theirGraph));

  for (const change of changes) {
    if (!selectedIds.has(change.id)) continue;
    // Read the id from the change, never by splitting targetKey: a Langflow edge
    // id embeds serialized handles and contains ":", so parsing truncated it and
    // the lookup missed — the edge was dropped with no error at all.
    const { targetKind, targetId } = change;

    if (targetKind === "node") {
      const theirNode = theirNodes.get(targetId);
      if (change.badge === "removed" && !theirNode) {
        nodes.delete(targetId);
      } else if (theirNode) {
        nodes.set(targetId, theirNode);
      }
      continue;
    }

    const theirEdge = theirEdges.get(targetId);
    if (change.badge === "removed" && !theirEdge) {
      edges.delete(targetId);
    } else if (theirEdge) {
      // A link they drew to a node they also added needs that node, and node and
      // edge are separate rows the person ticks separately. Ticking only the link
      // used to apply nothing at all while the footer still counted it, so the
      // endpoints it depends on come with it -- but only where I have no node of
      // that id, since replacing one of mine is a decision of its own.
      for (const endpoint of [theirEdge.source, theirEdge.target]) {
        if (nodes.has(endpoint)) continue;
        const theirNode = theirNodes.get(endpoint);
        if (theirNode) nodes.set(endpoint, theirNode);
      }
      edges.set(targetId, theirEdge);
    }
  }

  // An adopted edge whose endpoints were not adopted would dangle and break the canvas.
  const survivingEdges = [...edges.values()].filter(
    (edge) => nodes.has(edge.source) && nodes.has(edge.target),
  );

  return { nodes: [...nodes.values()], edges: survivingEdges };
};

/** Components both people changed: the only choices that cost something. */
export const contestedTargetKeys = (
  mine: FlowChange[],
  theirs: FlowChange[],
): Set<string> => {
  const mineKeys = new Set(mine.map((change) => change.targetKey));
  return new Set(
    theirs.map((change) => change.targetKey).filter((key) => mineKeys.has(key)),
  );
};
