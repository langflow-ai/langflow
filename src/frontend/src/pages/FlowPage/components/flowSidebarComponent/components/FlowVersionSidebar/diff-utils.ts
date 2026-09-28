import type {
  FlowVersionDiffSideRef,
  FlowVersionDiffSummary,
} from "@/types/flow/version";

/** Longest rendered value before the table cell clamps it. */
export const MAX_RENDERED_VALUE_CHARS = 400;

export type UnifiedDiffLineKind = "add" | "del" | "meta" | "ctx";

export type UnifiedDiffLine = {
  kind: UnifiedDiffLineKind;
  text: string;
};

export type DiffSummaryChip = {
  key: keyof FlowVersionDiffSummary;
  count: number;
  tone: "added" | "removed" | "modified" | "secret";
};

/**
 * Render a field value for the comparison table.
 *
 * Values arrive as arbitrary JSON. Objects and arrays are serialized so the two
 * columns stay visually comparable, and everything is clamped so one giant
 * prompt cannot blow out the dialog.
 */
export function formatDiffValue(value: unknown): string {
  if (value === undefined) return "";
  if (value === null) return "null";
  if (typeof value === "string") return clamp(value);
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  try {
    return clamp(JSON.stringify(value, null, 2) ?? "");
  } catch {
    return "[unserializable]";
  }
}

function clamp(text: string): string {
  return text.length > MAX_RENDERED_VALUE_CHARS
    ? `${text.slice(0, MAX_RENDERED_VALUE_CHARS)}…`
    : text;
}

/**
 * Classify each line of a server-rendered unified diff so it can be coloured.
 *
 * The backend sends the diff already rendered, so there is no diff library on
 * the client — this only assigns a kind per line.
 */
export function parseUnifiedDiffLines(
  unifiedDiff: string | null | undefined,
): UnifiedDiffLine[] {
  if (!unifiedDiff) return [];
  return unifiedDiff.split("\n").map((text) => ({
    kind: classifyDiffLine(text),
    text,
  }));
}

function classifyDiffLine(text: string): UnifiedDiffLineKind {
  if (
    text.startsWith("+++") ||
    text.startsWith("---") ||
    text.startsWith("@@")
  ) {
    return "meta";
  }
  if (text.startsWith("+")) return "add";
  if (text.startsWith("-")) return "del";
  return "ctx";
}

/** Build the non-zero summary chips, in a stable reading order. */
export function buildSummaryChips(
  summary: FlowVersionDiffSummary | undefined,
): DiffSummaryChip[] {
  if (!summary) return [];
  const candidates: DiffSummaryChip[] = [
    { key: "nodes_added", count: summary.nodes_added, tone: "added" },
    { key: "nodes_removed", count: summary.nodes_removed, tone: "removed" },
    { key: "nodes_modified", count: summary.nodes_modified, tone: "modified" },
    { key: "edges_added", count: summary.edges_added, tone: "added" },
    { key: "edges_removed", count: summary.edges_removed, tone: "removed" },
    { key: "secrets_changed", count: summary.secrets_changed, tone: "secret" },
  ];
  return candidates.filter((chip) => chip.count > 0);
}

/** Short label for one side of the comparison, e.g. "v3" or "Current". */
export function describeDiffSide(
  side: FlowVersionDiffSideRef | undefined,
  draftLabel: string,
): string {
  if (!side) return "";
  if (side.kind === "draft") return draftLabel;
  return side.version_tag ?? "";
}
