/**
 * Shared types for the image-annotation API (/api/v1/annotation-projects).
 *
 * The annotation result follows Label Studio's RectangleLabels format:
 * percentage coordinates (0-100) + per-region original_width/height, so
 * data can round-trip to Label Studio and convert to COCO unchanged.
 */

export interface AnnotationLabel {
  value: string;
  background?: string | null;
}

export interface AnnotationProjectType {
  id: string;
  name: string;
  description: string | null;
  labels: AnnotationLabel[];
  image_count: number;
  labeled_count: number;
  created_at: string;
  updated_at: string;
}

export interface AnnotationImageType {
  id: string;
  project_id: string;
  name: string;
  size: number;
  width: number | null;
  height: number | null;
  is_labeled: boolean;
  annotation_count: number;
  created_at: string;
  updated_at: string;
}

export interface AnnotationProjectDetailType extends AnnotationProjectType {
  images: AnnotationImageType[];
}

export interface AnnotationProjectCreateType {
  name: string;
  description?: string | null;
  labels: AnnotationLabel[];
}

export interface AnnotationProjectUpdateType {
  name?: string;
  description?: string | null;
  labels?: AnnotationLabel[];
}

export interface AnnotationImageUpdateType {
  name?: string;
  width?: number;
  height?: number;
}

/** `value` payload of one rectangle region (percentage coordinates). */
export interface AnnotationRegionValue {
  x: number;
  y: number;
  width: number;
  height: number;
  rotation?: number;
  rectanglelabels: string[];
  [key: string]: unknown;
}

/** One region entry in the Label-Studio-style `result` array. */
export interface AnnotationRegion {
  id: string;
  type: string;
  from_name: string;
  to_name: string;
  origin: string;
  original_width?: number | null;
  original_height?: number | null;
  image_rotation?: number;
  value: AnnotationRegionValue;
  [key: string]: unknown;
}

export interface AnnotationResultType {
  result: AnnotationRegion[];
  updated_at: string;
}

export interface AnnotationResultUpdateType {
  result: AnnotationRegion[];
  lead_time?: number;
}
