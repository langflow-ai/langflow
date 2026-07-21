/**
 * Shared types for the text-annotation API (/api/v1/text-annotation-projects).
 *
 * The annotation result follows Label Studio's text labeling formats:
 * - NER:            `labels` regions with character offsets
 *                   ({start, end, text, labels: [...]})
 * - classification: `choices` regions ({choices: [...]})
 *
 * so data can round-trip to Label Studio and export to BERT training formats
 * (CSV / CoNLL BIO) unchanged.
 */

export type TextAnnotationTaskType = "ner" | "classification";

export interface TextAnnotationLabel {
  value: string;
  background?: string | null;
}

export interface TextAnnotationProjectType {
  id: string;
  name: string;
  description: string | null;
  task_type: TextAnnotationTaskType;
  entity_labels: TextAnnotationLabel[];
  category_labels: TextAnnotationLabel[];
  task_count: number;
  labeled_count: number;
  created_at: string;
  updated_at: string;
}

/** `value` payload of one NER span region (character offsets). */
export interface TextSpanValue {
  start: number;
  end: number;
  text: string;
  labels: string[];
  [key: string]: unknown;
}

/** `value` payload of one classification choices region. */
export interface TextChoicesValue {
  choices: string[];
  [key: string]: unknown;
}

/** One region entry in the Label-Studio-style `result` array. */
export interface TextAnnotationRegion {
  id: string;
  type: string;
  from_name: string;
  to_name: string;
  origin: string;
  value: TextSpanValue | TextChoicesValue;
  [key: string]: unknown;
}

export interface TextAnnotationTaskItemType {
  id: string;
  project_id: string;
  name: string;
  text: string;
  source: string;
  result: TextAnnotationRegion[];
  is_labeled: boolean;
  created_at: string;
  updated_at: string;
}

export interface TextAnnotationProjectDetailType
  extends TextAnnotationProjectType {
  tasks: TextAnnotationTaskItemType[];
}

export interface TextAnnotationProjectCreateType {
  name: string;
  description?: string | null;
  task_type: TextAnnotationTaskType;
  entity_labels: TextAnnotationLabel[];
  category_labels: TextAnnotationLabel[];
}

export interface TextAnnotationProjectUpdateType {
  name?: string;
  description?: string | null;
  task_type?: TextAnnotationTaskType;
  entity_labels?: TextAnnotationLabel[];
  category_labels?: TextAnnotationLabel[];
}

export interface TextAnnotationTaskCreateType {
  text: string;
  name?: string | null;
}

export interface TextAnnotationResultType {
  result: TextAnnotationRegion[];
  updated_at: string;
}

export interface TextAnnotationImportResponseType {
  created: number;
  skipped: number;
}

export interface DatabaseImportPreviewRequestType {
  connection_uri: string;
  table_name: string;
  sample_size?: number;
}

export interface DatabaseImportPreviewResponseType {
  columns: string[];
  rows: Record<string, unknown>[];
}

export interface DatabaseImportRequestType {
  connection_uri: string;
  table_name: string;
  text_column: string;
  name_column?: string | null;
  limit?: number;
  offset?: number;
}

export type TextAnnotationExportFormat = "json" | "csv" | "conll";
