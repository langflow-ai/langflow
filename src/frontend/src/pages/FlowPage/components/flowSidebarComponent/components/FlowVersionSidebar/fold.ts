import type { RecordedOperation, RevisionEntry } from "@/types/flow/revision";
import {
  type DescribeOptions,
  describeOperation,
  summarizeOperations,
} from "@/utils/flow-operations/describe";
import { ID_NAMES } from "@/utils/flow-operations/names";

type TFunction = (key: string, opts?: object) => string;

/**
 * Causes whose changes the timeline folds into one line: one action rewrote
 * a lot (a component update, a code edit, a restore), so its entry reads as
 * that action, with the individual changes one click away.
 */
export const FOLDED_CAUSES = [
  "upgrade_component",
  "edit_code",
  "file_sync",
  "restore",
  "assistant",
  "repair",
] as const;

export type FoldedCause = (typeof FOLDED_CAUSES)[number];

const TEMPLATE_PATH = ["data", "node", "template"];

type Update = { id: string; path: unknown[] };

function isFoldedCause(cause: unknown): cause is FoldedCause {
  return FOLDED_CAUSES.includes(cause as FoldedCause);
}

/** The cause an entry folds under: one every operation in it shares. */
export function foldedCause(
  operations: RecordedOperation[] | null | undefined,
): FoldedCause | null {
  if (!operations || operations.length === 0) return null;
  const [{ cause }] = operations;
  if (!isFoldedCause(cause)) return null;
  return operations.every((operation) => operation.cause === cause)
    ? cause
    : null;
}

function updatesOf(operation: RecordedOperation): Update[] {
  const { type, updates } = operation.operation;
  return (type === "update_nodes" || type === "update_edges") &&
    Array.isArray(updates)
    ? (updates as Update[])
    : [];
}

// What one write changed, coarse enough that a field's value, its toggles and
// its definition count as one changed field.
function changedKey(update: Update): string {
  const path = Array.isArray(update.path) ? update.path : [];
  const underTemplate =
    path.length > TEMPLATE_PATH.length &&
    TEMPLATE_PATH.every((part, index) => path[index] === part);
  const target = underTemplate ? path.slice(0, TEMPLATE_PATH.length + 1) : path;
  return `${update.id}\u0000${JSON.stringify(target)}`;
}

function listLength(value: unknown): number {
  return Array.isArray(value) ? value.length : 0;
}

/**
 * How many things an entry changed: distinct fields for writes inside
 * components and connections, and one per component or connection added or
 * removed. `onlyFields` says whether every change was a field write.
 */
export function countChanges(operations: RecordedOperation[]): {
  count: number;
  onlyFields: boolean;
} {
  const fields = new Set<string>();
  let others = 0;
  for (const recorded of operations) {
    const { operation } = recorded;
    switch (operation.type) {
      case "update_nodes":
      case "update_edges":
        for (const update of updatesOf(recorded))
          fields.add(changedKey(update));
        break;
      case "add_nodes":
        others += listLength(operation.nodes);
        break;
      case "add_edges":
        others += listLength(operation.edges);
        break;
      case "delete_nodes":
      case "delete_edges":
        others += listLength(operation.ids);
        break;
      default:
        others += 1;
    }
  }
  return { count: fields.size + others, onlyFields: others === 0 };
}

// The components an entry's writes touched, by id, in the order first seen.
function touchedNodes(operations: RecordedOperation[]): string[] {
  const ids = new Set<string>();
  for (const recorded of operations) {
    const { operation } = recorded;
    if (operation.type === "update_nodes") {
      for (const update of updatesOf(recorded)) ids.add(update.id);
    } else if (operation.type === "add_nodes") {
      for (const node of (operation.nodes as { id: string }[]) ?? []) {
        ids.add(node.id);
      }
    } else if (operation.type === "delete_nodes") {
      for (const id of (operation.ids as string[]) ?? []) ids.add(id);
    }
  }
  return [...ids];
}

/**
 * One line for an entry whose operations share a folded cause, such as
 * "Alice updated Agent; 42 fields changed". Null for any other entry.
 */
export function foldedSummary(
  entry: Pick<RevisionEntry, "operations" | "actors">,
  t: TFunction,
  options: DescribeOptions = {},
): string | null {
  const operations = entry.operations;
  const cause = foldedCause(operations);
  if (!cause || !operations) return null;
  const author =
    entry.actors
      .map((actor) => actor.username ?? t("flowHistory.unknownAuthor"))
      .join(", ") || t("flowHistory.unknownAuthor");
  const nodes = touchedNodes(operations);
  const name =
    nodes.length === 1
      ? (options.names ?? ID_NAMES).node(nodes[0])
      : t("flowHistory.fold.components", { count: nodes.length });
  const { count, onlyFields } = countChanges(operations);
  return t("flowHistory.fold.line", {
    action: t(`flowHistory.fold.${cause}`, { author, name }),
    changes: onlyFields
      ? t("flowHistory.fold.fieldsChanged", { count })
      : t("flowHistory.changes", { count }),
  });
}

/** An entry's summary: its folded line, or its first changes. */
export function summarizeEntry(
  entry: Pick<RevisionEntry, "operations" | "actors">,
  t: TFunction,
  options: DescribeOptions = {},
): string | null {
  if (!entry.operations) return null;
  return (
    foldedSummary(entry, t, options) ??
    summarizeOperations(entry.operations, t, options)
  );
}

/** Each change of an entry as its own sentence, for a folded entry's details. */
export function describeChanges(
  operations: RecordedOperation[],
  t: TFunction,
  options: DescribeOptions = {},
): string[] {
  return operations.flatMap((operation) =>
    describeOperation(operation, t, options),
  );
}
