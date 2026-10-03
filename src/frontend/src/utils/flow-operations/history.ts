import type { RecordedOperation, RevisionEntry } from "@/types/flow/revision";
import { applyFlowOperations, type FlowGraph } from "./apply";

/**
 * A flow's retained history, replayed so every revision can be shown at once.
 *
 * `graphs[i]` is the flow at revision `baseRevision + i`, and `operations[i]`
 * is the recorded operation that turned `graphs[i]` into `graphs[i + 1]`.
 * Operations are copy-on-write, so consecutive graphs share every node an
 * operation did not touch, and stepping either way is a lookup.
 */
export type HistoryTimeline = {
  flowId: string;
  baseRevision: number;
  graphs: FlowGraph[];
  operations: RecordedOperation[];
  /** Retained entries, oldest first. */
  entries: RevisionEntry[];
};

export function lastRevision(timeline: HistoryTimeline): number {
  return timeline.baseRevision + timeline.graphs.length - 1;
}

/** The flow at `revision`, or null when the timeline does not reach it. */
export function graphAt(
  timeline: HistoryTimeline,
  revision: number,
): FlowGraph | null {
  return timeline.graphs[revision - timeline.baseRevision] ?? null;
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
 * Replay `operations` forward from `base`, keeping the graph after each one.
 *
 * Stops at the first operation that is missing or does not apply, so the
 * timeline covers what could be replayed rather than nothing. The operations
 * come from the history API with secrets removed, so they are applied in
 * redacted mode.
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
  const graphs: FlowGraph[] = [base];
  const operations: RecordedOperation[] = [];
  for (;;) {
    const operation = byRevision.get(baseRevision + graphs.length);
    if (!operation) break;
    try {
      graphs.push(
        applyFlowOperations(graphs[graphs.length - 1], [operation.operation], {
          redacted: true,
        }).flowData,
      );
    } catch {
      break;
    }
    operations.push(operation);
  }
  return { flowId, baseRevision, graphs, operations, entries };
}
