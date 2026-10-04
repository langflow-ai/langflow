import type { RecordedOperation } from "@/types/flow/revision";
import { type FlowNames, ID_NAMES } from "./names";

type TFunction = (key: string, opts?: object) => string;

const TEMPLATE_PATH = ["data", "node", "template"];
const OUTPUTS_PATH = ["data", "node", "outputs"];
// A table row is `template.<field>.value.{"id": ...}`.
const ROW_INDEX = TEMPLATE_PATH.length + 2;
const ROW_POSITION = "_pos";

type Segment = unknown;
type Update = {
  id: string;
  op: string;
  path: Segment[];
  value?: unknown;
  from_type?: string;
};

export type DescribeOptions = {
  /** A template field's label, such as "API Key" for `api_key`, if known. */
  fieldLabel?: (nodeId: string, field: string) => string | undefined;
  /** Names for the nodes and edges operations mention by id. */
  names?: FlowNames;
};

/** `sender_name` → "Sender name", for fields whose label is unknown. */
export function humanizeField(field: string): string {
  const words = field.replace(/[_-]+/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/**
 * Field labels from a graph's templates. A node deleted since has no entry,
 * so its fields fall back to `humanizeField`.
 */
export function fieldLabelsFrom(
  graph: { nodes?: unknown } | null | undefined,
): NonNullable<DescribeOptions["fieldLabel"]> {
  const templates = new Map<string, Record<string, unknown>>();
  const nodes = (Array.isArray(graph?.nodes) ? graph.nodes : []) as {
    id?: unknown;
    data?: { node?: { template?: unknown } };
  }[];
  for (const node of nodes) {
    const template = node?.data?.node?.template;
    if (
      typeof node?.id === "string" &&
      template &&
      typeof template === "object"
    )
      templates.set(node.id, template as Record<string, unknown>);
  }
  return (nodeId, field) => {
    const entry = templates.get(nodeId)?.[field] as
      | { display_name?: unknown }
      | undefined;
    return typeof entry?.display_name === "string" && entry.display_name
      ? entry.display_name
      : undefined;
  };
}

function startsWith(path: Segment[], prefix: string[]): boolean {
  return prefix.every((part, index) => path[index] === part);
}

function selectorKey(segment: Segment): string | null {
  if (segment === null || typeof segment !== "object") return null;
  const { id, key } = segment as { id?: unknown; key?: unknown };
  return typeof id === "string" ? id : typeof key === "string" ? key : null;
}

/** The template field a path writes into, or null. */
export function templateFieldOf(path: Segment[]): string | null {
  const field = path[TEMPLATE_PATH.length];
  return startsWith(path, TEMPLATE_PATH) && typeof field === "string"
    ? field
    : null;
}

/** The output a path writes into (`outputs.{"key": name}`), or null. */
export function outputOf(path: Segment[]): string | null {
  return startsWith(path, OUTPUTS_PATH)
    ? selectorKey(path[OUTPUTS_PATH.length])
    : null;
}

/**
 * What a write to a table row does to the row: adds it (the whole row at a
 * new id), removes it, or moves it (its position). Null for a cell edit or
 * any write outside a table row.
 */
export function rowChangeOf(
  update: Pick<Update, "op" | "path">,
): "added" | "removed" | "moved" | null {
  const { path } = update;
  if (
    templateFieldOf(path) === null ||
    path[TEMPLATE_PATH.length + 1] !== "value" ||
    selectorKey(path[ROW_INDEX]) === null
  )
    return null;
  if (path.length === ROW_INDEX + 1)
    return update.op === "delete_field" ? "removed" : "added";
  return path.length === ROW_INDEX + 2 && path[ROW_INDEX + 1] === ROW_POSITION
    ? "moved"
    : null;
}

/**
 * Describe one recorded operation as short sentences for the history timeline.
 *
 * Operations carry ids only; nodes are named by `options.names`, so a node
 * renamed or deleted since reads by the name the flow or history last gave it.
 */
export function describeOperation(
  recorded: RecordedOperation,
  t: TFunction,
  options: DescribeOptions = {},
): string[] {
  const { operation } = recorded;
  const names = options.names ?? ID_NAMES;
  switch (operation.type) {
    case "add_nodes": {
      const ids = (operation.nodes as { id: string }[]).map((node) => node.id);
      return ids.length === 1
        ? [t("flowHistory.op.addedNode", { name: names.node(ids[0]) })]
        : [t("flowHistory.op.addedNodes", { count: ids.length })];
    }
    case "delete_nodes": {
      const ids = operation.ids as string[];
      return ids.length === 1
        ? [t("flowHistory.op.deletedNode", { name: names.node(ids[0]) })]
        : [t("flowHistory.op.deletedNodes", { count: ids.length })];
    }
    case "add_edges":
      return (operation.edges as { source: string; target: string }[]).map(
        (edge) =>
          t("flowHistory.op.connected", {
            source: names.node(edge.source),
            target: names.node(edge.target),
          }),
      );
    case "delete_edges":
      return (operation.ids as string[]).map((id) => {
        const ends = names.edge(id);
        return ends
          ? t("flowHistory.op.disconnected", {
              source: names.node(ends.source),
              target: names.node(ends.target),
            })
          : t("flowHistory.op.removedConnection");
      });
    case "update_edges": {
      const ids = [
        ...new Set((operation.updates as Update[]).map((update) => update.id)),
      ];
      return ids.map((id) => {
        const ends = names.edge(id);
        return ends
          ? t("flowHistory.op.updatedConnection", {
              source: names.node(ends.source),
              target: names.node(ends.target),
            })
          : t("flowHistory.op.updatedAConnection");
      });
    }
    case "update_nodes":
      return describeUpdates(operation.updates as Update[], names, t, options);
    case "update_metadata":
      return [t("flowHistory.op.updatedFlowSettings")];
    default:
      return [];
  }
}

const ROW_KEYS = {
  added: "flowHistory.op.addedRows",
  removed: "flowHistory.op.removedRows",
  moved: "flowHistory.op.movedRows",
};

function describeUpdates(
  updates: Update[],
  names: FlowNames,
  t: TFunction,
  options: DescribeOptions,
): string[] {
  const label = (id: string, field: string) =>
    options.fieldLabel?.(id, field) ?? humanizeField(field);
  const byNode = new Map<string, Update[]>();
  for (const update of updates) {
    byNode.set(update.id, [...(byNode.get(update.id) ?? []), update]);
  }
  const sentences: string[] = [];
  for (const [id, nodeUpdates] of byNode) {
    const name = names.node(id);
    const fields = new Set<string>();
    // Rows added, removed or moved, counted per field.
    const rows = new Map<string, number>();
    const own: string[] = [];
    for (const update of nodeUpdates) {
      const field = templateFieldOf(update.path);
      const row = rowChangeOf(update);
      const output = outputOf(update.path);
      if (field !== null && row !== null) {
        const key = `${row}\u0000${field}`;
        rows.set(key, (rows.get(key) ?? 0) + 1);
      } else if (field !== null) {
        fields.add(label(id, field));
      } else if (
        output !== null &&
        update.path[update.path.length - 1] === "hidden"
      ) {
        own.push(
          t(
            update.op === "set_field" && update.value === true
              ? "flowHistory.op.hidOutput"
              : "flowHistory.op.showedOutput",
            { output: humanizeField(output), name },
          ),
        );
      }
    }
    const typeChange = nodeUpdates.find(
      (update) => update.from_type && templateFieldOf(update.path),
    );
    if (typeChange) {
      sentences.push(
        t("flowHistory.op.changedFieldType", {
          field: label(id, templateFieldOf(typeChange.path) as string),
          name,
          from: typeChange.from_type,
          to: jsonTypeName(typeChange.value),
        }),
      );
    } else if (fields.size > 0) {
      sentences.push(
        t("flowHistory.op.editedFields", {
          fields: [...fields].join(", "),
          name,
        }),
      );
    }
    for (const [key, count] of rows) {
      const [row, field] = key.split("\u0000") as [
        keyof typeof ROW_KEYS,
        string,
      ];
      sentences.push(
        t(ROW_KEYS[row], { count, field: label(id, field), name }),
      );
    }
    sentences.push(...own);
    if (fields.size > 0 || rows.size > 0 || own.length > 0) continue;
    if (nodeUpdates.every((update) => update.path[0] === "position")) {
      sentences.push(t("flowHistory.op.movedNode", { name }));
    } else {
      sentences.push(t("flowHistory.op.editedNode", { name }));
    }
  }
  return sentences;
}

function jsonTypeName(value: unknown): string {
  if (value === null) return "null";
  if (Array.isArray(value)) return "array";
  return typeof value;
}

/** Summarize an entry's operations in one line: the first two changes and a count of the rest. */
export function summarizeOperations(
  operations: RecordedOperation[],
  t: TFunction,
  options: DescribeOptions = {},
): string {
  const sentences = operations.flatMap((operation) =>
    describeOperation(operation, t, options),
  );
  if (sentences.length === 0) return t("flowHistory.op.noChanges");
  const shown = sentences.slice(0, 2).join("; ");
  const rest = sentences.length - 2;
  return rest > 0
    ? t("flowHistory.summaryWithMore", { summary: shown, count: rest })
    : shown;
}
