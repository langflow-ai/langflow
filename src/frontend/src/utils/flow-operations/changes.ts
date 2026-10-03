import type { RecordedOperation, RevisionActor } from "@/types/flow/revision";
import { entryContaining, type HistoryTimeline, operationAt } from "./history";

const TEMPLATE_PATH = ["data", "node", "template"];

type NodeUpdate = { id: string; path: (string | number)[] };

export type NodeChange = {
  /** The last person to change the node. */
  actor: RevisionActor;
  /** Added here, rather than only edited. */
  added: boolean;
  /** Template fields edited, each with its last writer. */
  fields: Map<string, RevisionActor>;
  /** The operations that touched the node, narrowed to it, oldest first. */
  operations: RecordedOperation[];
};

export type RemovedNode = { id: string; name: string; actor: RevisionActor };

export type RemovedEdge = {
  id: string;
  /** Endpoint names as recorded, or null when the recording has none. */
  source: string | null;
  target: string | null;
  actor: RevisionActor;
};

/** What a run of recorded operations changed, and who changed it last. */
export type FlowChanges = {
  /** Nodes added or edited that still exist afterwards. */
  nodes: Map<string, NodeChange>;
  /** Edges added that still exist afterwards, with who added them. */
  edges: Map<string, RevisionActor>;
  removedNodes: RemovedNode[];
  /** Connections removed on their own, not with a removed node. */
  removedEdges: RemovedEdge[];
};

function templateField(path: (string | number)[]): string | null {
  const isTemplate = TEMPLATE_PATH.every((part, index) => path[index] === part);
  return isTemplate && path.length > TEMPLATE_PATH.length
    ? String(path[TEMPLATE_PATH.length])
    : null;
}

function narrowed(
  recorded: RecordedOperation,
  operation: Record<string, unknown>,
): RecordedOperation {
  return {
    ...recorded,
    operation: { ...recorded.operation, ...operation },
  };
}

/**
 * Which nodes, template fields and edges `operations` changed, and by whom.
 *
 * Read straight from the recorded operations, oldest first, so a later
 * operation wins: the last writer is the one shown, a node added and then
 * deleted counts only as removed, and one deleted and added back counts as
 * added.
 */
export function changesFrom(operations: RecordedOperation[]): FlowChanges {
  const nodes = new Map<string, NodeChange>();
  const edges = new Map<string, RevisionActor>();
  const removedNodes = new Map<string, RemovedNode>();
  const removedEdges = new Map<
    string,
    RemovedEdge & { sourceId?: string; targetId?: string }
  >();

  const touch = (id: string, actor: RevisionActor, added: boolean) => {
    const change: NodeChange = nodes.get(id) ?? {
      actor,
      added,
      fields: new Map(),
      operations: [],
    };
    change.actor = actor;
    change.added ||= added;
    nodes.set(id, change);
    return change;
  };

  for (const recorded of operations) {
    const { operation, actor, labels } = recorded;
    switch (operation.type) {
      case "add_nodes":
        for (const node of operation.nodes as { id: string }[]) {
          removedNodes.delete(node.id);
          touch(node.id, actor, true).operations.push(
            narrowed(recorded, { nodes: [node] }),
          );
        }
        break;
      case "update_nodes": {
        const updates = operation.updates as NodeUpdate[];
        for (const id of new Set(updates.map((update) => update.id))) {
          const own = updates.filter((update) => update.id === id);
          const change = touch(id, actor, false);
          change.operations.push(narrowed(recorded, { updates: own }));
          for (const update of own) {
            const field = templateField(update.path);
            if (field !== null) change.fields.set(field, actor);
          }
        }
        break;
      }
      case "delete_nodes":
        for (const id of operation.ids as string[]) {
          nodes.delete(id);
          removedNodes.set(id, {
            id,
            name: labels.nodes?.[id] ?? id,
            actor,
          });
        }
        break;
      case "add_edges":
        for (const edge of operation.edges as { id: string }[]) {
          removedEdges.delete(edge.id);
          edges.set(edge.id, actor);
        }
        break;
      case "delete_edges":
        for (const id of operation.ids as string[]) {
          edges.delete(id);
          const ends = labels.edges?.[id];
          removedEdges.set(id, {
            id,
            source: ends ? (labels.nodes?.[ends.source] ?? ends.source) : null,
            target: ends ? (labels.nodes?.[ends.target] ?? ends.target) : null,
            actor,
            sourceId: ends?.source,
            targetId: ends?.target,
          });
        }
        break;
    }
  }

  return {
    nodes,
    edges,
    removedNodes: [...removedNodes.values()],
    removedEdges: [...removedEdges.values()]
      .filter(
        (edge) =>
          !(edge.sourceId && removedNodes.has(edge.sourceId)) &&
          !(edge.targetId && removedNodes.has(edge.targetId)),
      )
      .map(({ sourceId: _source, targetId: _target, ...edge }) => edge),
  };
}

/**
 * The operations a preview at `revision` shows the changes of: at an entry's
 * end, everything in the entry; inside it, the one that produced `revision`.
 */
export function operationsAt(
  timeline: HistoryTimeline,
  revision: number,
): RecordedOperation[] {
  const entry = entryContaining(timeline.entries, revision);
  if (entry?.end_revision === revision) {
    const start = Math.max(entry.start_revision - timeline.baseRevision - 1, 0);
    return timeline.operations.slice(start, revision - timeline.baseRevision);
  }
  const operation = operationAt(timeline, revision);
  return operation ? [operation] : [];
}

const cache = new WeakMap<HistoryTimeline, Map<number, FlowChanges>>();

/**
 * `changesFrom(operationsAt(timeline, revision))`, kept per timeline so
 * every node on the canvas reads the same object.
 */
export function changesAt(
  timeline: HistoryTimeline,
  revision: number,
): FlowChanges {
  let byRevision = cache.get(timeline);
  if (!byRevision) {
    byRevision = new Map();
    cache.set(timeline, byRevision);
  }
  let changes = byRevision.get(revision);
  if (!changes) {
    changes = changesFrom(operationsAt(timeline, revision));
    byRevision.set(revision, changes);
  }
  return changes;
}

/**
 * Consecutive operations by the same person, merged, for listing who did
 * what in order.
 */
export function groupByActor(
  operations: RecordedOperation[],
): { actor: RevisionActor; operations: RecordedOperation[] }[] {
  const groups: { actor: RevisionActor; operations: RecordedOperation[] }[] =
    [];
  for (const operation of operations) {
    const last = groups[groups.length - 1];
    if (last && last.actor.id === operation.actor.id)
      last.operations.push(operation);
    else groups.push({ actor: operation.actor, operations: [operation] });
  }
  return groups;
}
