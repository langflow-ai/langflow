import type {
  AnnotationLabel,
  AnnotationProjectType,
  AnnotationRegion,
} from "@/types/annotation";

export type {
  AnnotationImageType,
  AnnotationLabel,
  AnnotationProjectCreateType,
  AnnotationProjectDetailType,
  AnnotationProjectType,
  AnnotationProjectUpdateType,
  AnnotationRegion,
  AnnotationRegionValue,
  AnnotationResultType,
} from "@/types/annotation";

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

export function colorForLabel(
  labelValue: string,
  labels: AnnotationLabel[],
): string {
  const idx = labels.findIndex((l) => l.value === labelValue);
  if (idx === -1) return LABEL_COLORS[0] ?? "#ef4444";
  return (
    labels[idx]?.background ??
    LABEL_COLORS[idx % LABEL_COLORS.length] ??
    "#ef4444"
  );
}

export function defaultLabelColor(index: number): string {
  return LABEL_COLORS[index % LABEL_COLORS.length] ?? "#ef4444";
}

/** Region id in the Label Studio style (~10 random chars). */
export function genRegionId(): string {
  return Math.random().toString(36).slice(2, 12);
}

export interface RectPct {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Build a Label-Studio-compatible RectangleLabels region. */
export function createRegion(
  rect: RectPct,
  label: string,
  naturalWidth: number | null,
  naturalHeight: number | null,
): AnnotationRegion {
  return {
    id: genRegionId(),
    type: "rectanglelabels",
    from_name: "label",
    to_name: "image",
    origin: "manual",
    original_width: naturalWidth,
    original_height: naturalHeight,
    image_rotation: 0,
    value: {
      x: rect.x,
      y: rect.y,
      width: rect.width,
      height: rect.height,
      rotation: 0,
      rectanglelabels: label ? [label] : [],
    },
  };
}

export function computeProgress(project: AnnotationProjectType): {
  done: number;
  total: number;
} {
  return { done: project.labeled_count, total: project.image_count };
}
