import type { RecordedOperation, RevisionEntry } from "@/types/flow/revision";
import {
  type ApplyOptions,
  applyFlowOperations,
  type FlowGraph,
  type FlowOperation,
} from "./apply";
import { collectHistoryNames, type HistoryNames } from "./names";

// Operations from the history API have literal secrets removed, so they are
// replayed in redacted mode.
const FORWARD: ApplyOptions = { redacted: true };
const BACKWARD: ApplyOptions = { redacted: true, restoring: true };

/**
 * A flow's retained history, replayed so any revision can be shown.
 *
 * Playback holds one graph. Replaying an operation forward also records the
 * operations that undo it, read from the state it replaced, so stepping back
 * applies those and a jump applies whatever lies in between. Keeping the
 * inverses costs about what the operations do; a graph per revision would
 * cost a copy of every node each one touched.
 */
export type HistoryTimeline = {
  flowId: string;
  baseRevision: number;
  /** `operations[i]` produced revision `baseRevision + i + 1`. */
  operations: RecordedOperation[];
  /** Retained entries, oldest first. */
  entries: RevisionEntry[];
  /** Names the history shows, for nodes and edges the flow no longer has. */
  names: HistoryNames;
  /** The graph playback holds and the revision it is at. Moved by `graphAt`. */
  cursor: { revision: number; graph: FlowGraph };
  /** `inverses[i]` undoes `operations[i]`. */
  inverses: FlowOperation[][];
};

export function lastRevision(timeline: HistoryTimeline): number {
  return timeline.baseRevision + timeline.operations.length;
}

function stepForward(timeline: HistoryTimeline): void {
  const { cursor } = timeline;
  const index = cursor.revision - timeline.baseRevision;
  cursor.graph = applyFlowOperations(
    cursor.graph,
    [timeline.operations[index].operation],
    FORWARD,
  ).flowData;
  cursor.revision += 1;
}

function stepBack(timeline: HistoryTimeline): void {
  const { cursor } = timeline;
  const index = cursor.revision - timeline.baseRevision - 1;
  cursor.graph = applyFlowOperations(
    cursor.graph,
    timeline.inverses[index],
    BACKWARD,
  ).flowData;
  cursor.revision -= 1;
}

/**
 * The flow at `revision`, or null when the timeline does not reach it.
 *
 * Moves playback there: forward by replaying the operations in between,
 * back by applying their inverses. The graph returned is never changed
 * afterwards, so it stays valid after playback moves on.
 */
export function graphAt(
  timeline: HistoryTimeline,
  revision: number,
): FlowGraph | null {
  if (revision < timeline.baseRevision || revision > lastRevision(timeline))
    return null;
  try {
    while (timeline.cursor.revision < revision) stepForward(timeline);
    while (timeline.cursor.revision > revision) stepBack(timeline);
  } catch {
    // Every step was replayed once already, so this does not happen; if it
    // does, playback stays at the last revision it reached.
    return null;
  }
  return timeline.cursor.graph;
}

/** The operation that produced `revision`, or null at the base. */
export function operationAt(
  timeline: HistoryTimeline,
  revision: number,
): RecordedOperation | null {
  return timeline.operations[revision - timeline.baseRevision - 1] ?? null;
}

/** The entry whose revisions include `revision`. */
export function entryContaining(
  entries: RevisionEntry[],
  revision: number,
): RevisionEntry | undefined {
  return entries.find(
    (entry) =>
      entry.start_revision <= revision && revision <= entry.end_revision,
  );
}

/**
 * Replay `operations` forward from `base`, recording each one's inverse.
 *
 * Stops at the first operation that is missing or does not apply, so the
 * timeline covers what could be replayed rather than nothing. Playback ends
 * at the last revision replayed.
 */
export function buildHistoryTimeline({
  flowId,
  baseRevision,
  base,
  entries,
}: {
  flowId: string;
  baseRevision: number;
  base: FlowGraph;
  entries: RevisionEntry[];
}): HistoryTimeline {
  const byRevision = new Map<number, RecordedOperation>();
  for (const entry of entries) {
    for (const operation of entry.operations ?? [])
      byRevision.set(operation.revision, operation);
  }
  const operations: RecordedOperation[] = [];
  const inverses: FlowOperation[][] = [];
  let graph = base;
  for (;;) {
    const operation = byRevision.get(baseRevision + operations.length + 1);
    if (!operation) break;
    try {
      const result = applyFlowOperations(graph, [operation.operation], {
        ...FORWARD,
        inverse: true,
      });
      graph = result.flowData;
      inverses.push(result.inverseOperations![0]);
    } catch {
      break;
    }
    operations.push(operation);
  }
  return {
    flowId,
    baseRevision,
    operations,
    entries,
    names: collectHistoryNames(base, operations),
    cursor: { revision: baseRevision + operations.length, graph },
    inverses,
  };
}
