import type { RecordedOperation } from "@/types/flow/revision";

type TFunction = (key: string, opts?: object) => string;

const TEMPLATE_PATH = ["data", "node", "template"];

type Labels = RecordedOperation["labels"];

export type DescribeOptions = {
  /** A template field's label, such as "API Key" for `api_key`, if known. */
  fieldLabel?: (nodeId: string, field: string) => string | undefined;
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

function nodeName(labels: Labels, id: string): string {
  return labels.nodes?.[id] ?? id;
}

function fieldOf(path: (string | number)[]): string | null {
  const isTemplate = TEMPLATE_PATH.every((part, index) => path[index] === part);
  return isTemplate && path.length > TEMPLATE_PATH.length
    ? String(path[TEMPLATE_PATH.length])
    : null;
}

/**
 * Describe one recorded operation as short sentences for the history timeline.
 *
 * Names come from the labels recorded with the operation, so a node that was
 * renamed or deleted since still reads as it did at the time.
 */
export function describeOperation(
  recorded: RecordedOperation,
  t: TFunction,
  options: DescribeOptions = {},
): string[] {
  const { operation, labels } = recorded;
  switch (operation.type) {
    case "add_nodes": {
      const ids = (operation.nodes as { id: string }[]).map((node) => node.id);
      return ids.length === 1
        ? [t("flowHistory.op.addedNode", { name: nodeName(labels, ids[0]) })]
        : [t("flowHistory.op.addedNodes", { count: ids.length })];
    }
    case "delete_nodes": {
      const ids = operation.ids as string[];
      return ids.length === 1
        ? [t("flowHistory.op.deletedNode", { name: nodeName(labels, ids[0]) })]
        : [t("flowHistory.op.deletedNodes", { count: ids.length })];
    }
    case "add_edges":
      return (operation.edges as { source: string; target: string }[]).map(
        (edge) =>
          t("flowHistory.op.connected", {
            source: nodeName(labels, edge.source),
            target: nodeName(labels, edge.target),
          }),
      );
    case "delete_edges":
      return (operation.ids as string[]).map((id) => {
        const edge = labels.edges?.[id];
        return edge
          ? t("flowHistory.op.disconnected", {
              source: nodeName(labels, edge.source),
              target: nodeName(labels, edge.target),
            })
          : t("flowHistory.op.removedConnection");
      });
    case "update_nodes":
      return describeUpdates(
        operation.updates as {
          id: string;
          op: string;
          path: (string | number)[];
          value?: unknown;
          from_type?: string;
        }[],
        labels,
        t,
        options,
      );
    case "update_metadata":
      return [t("flowHistory.op.updatedFlowSettings")];
    default:
      return [];
  }
}

function describeUpdates(
  updates: {
    id: string;
    op: string;
    path: (string | number)[];
    value?: unknown;
    from_type?: string;
  }[],
  labels: Labels,
  t: TFunction,
  options: DescribeOptions,
): string[] {
  const label = (id: string, field: string) =>
    options.fieldLabel?.(id, field) ?? humanizeField(field);
  const byNode = new Map<string, typeof updates>();
  for (const update of updates) {
    byNode.set(update.id, [...(byNode.get(update.id) ?? []), update]);
  }
  const sentences: string[] = [];
  for (const [id, nodeUpdates] of byNode) {
    const name = nodeName(labels, id);
    const fields = [
      ...new Set(
        nodeUpdates
          .map((update) => fieldOf(update.path))
          .filter((field): field is string => field !== null)
          .map((field) => label(id, field)),
      ),
    ];
    const typeChange = nodeUpdates.find((update) => update.from_type);
    if (typeChange && fieldOf(typeChange.path)) {
      sentences.push(
        t("flowHistory.op.changedFieldType", {
          field: label(id, fieldOf(typeChange.path) as string),
          name,
          from: typeChange.from_type,
          to: jsonTypeName(typeChange.value),
        }),
      );
    } else if (fields.length > 0) {
      sentences.push(
        t("flowHistory.op.editedFields", { fields: fields.join(", "), name }),
      );
    } else if (nodeUpdates.every((update) => update.path[0] === "position")) {
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
