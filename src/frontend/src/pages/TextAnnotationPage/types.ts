import type {
  TextAnnotationRegion,
  TextAnnotationTaskItemType,
  TextChoicesValue,
  TextSpanValue,
} from "@/types/text-annotation";

/** Editor view-model for one NER span (flattened from the LS region shape). */
export interface TextSpan {
  id: string;
  start: number;
  end: number;
  text: string;
  label: string;
}

export const LABEL_COLORS = [
  "#ef4444",
  "#f97316",
  "#eab308",
  "#22c55e",
  "#06b6d4",
  "#3b82f6",
  "#8b5cf6",
  "#ec4899",
];

export function genSpanId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `id-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

// --------------------------------------------------------------------------- //
// Label-Studio result <-> editor view-model converters
// --------------------------------------------------------------------------- //

export function regionsToSpans(result: TextAnnotationRegion[]): TextSpan[] {
  const spans: TextSpan[] = [];
  for (const region of result ?? []) {
    if (region.type !== "labels") continue;
    const value = region.value as TextSpanValue;
    if (typeof value.start !== "number" || typeof value.end !== "number")
      continue;
    const label = value.labels?.[0];
    if (!label) continue;
    spans.push({
      id: region.id,
      start: value.start,
      end: value.end,
      text: value.text ?? "",
      label,
    });
  }
  return spans;
}

export function regionsToCategories(result: TextAnnotationRegion[]): string[] {
  const categories: string[] = [];
  for (const region of result ?? []) {
    if (region.type !== "choices") continue;
    const value = region.value as TextChoicesValue;
    for (const choice of value.choices ?? []) {
      if (!categories.includes(choice)) categories.push(choice);
    }
  }
  return categories;
}

export function spansToRegions(spans: TextSpan[]): TextAnnotationRegion[] {
  return spans.map((span) => ({
    id: span.id,
    type: "labels",
    from_name: "label",
    to_name: "text",
    origin: "manual",
    value: {
      start: span.start,
      end: span.end,
      text: span.text,
      labels: [span.label],
    },
  }));
}

export function categoriesToRegions(
  categories: string[],
): TextAnnotationRegion[] {
  if (categories.length === 0) return [];
  return [
    {
      id: genSpanId(),
      type: "choices",
      from_name: "choice",
      to_name: "text",
      origin: "manual",
      value: { choices: categories },
    },
  ];
}

export function computeProgress(tasks: TextAnnotationTaskItemType[]): {
  done: number;
  total: number;
} {
  return {
    total: tasks.length,
    done: tasks.filter((task) => task.is_labeled).length,
  };
}
