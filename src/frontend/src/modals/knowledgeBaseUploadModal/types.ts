import type { ModelOption } from "@/components/core/parameterRenderComponent/components/modelInputComponent";

export interface KnowledgeBaseUploadModalProps {
  open?: boolean;
  setOpen?: (open: boolean) => void;
  onSubmit?: (data: KnowledgeBaseFormData) => void;
  existingKnowledgeBase?: {
    name: string;
    embeddingProvider?: string;
    embeddingModel?: string;
    chunkSize?: number;
    chunkOverlap?: number;
    separator?: string;
    columnConfig?: ColumnConfigRow[];
  };
  hideAdvanced?: boolean;
  existingKnowledgeBaseNames?: string[];
}

export interface ColumnConfigRow {
  column_name: string;
  vectorize: boolean;
  identifier: boolean;
}

export interface KnowledgeBaseFormData {
  sourceName: string;
  files: File[];
  embeddingModel: ModelOption[] | null;
  chunkSize?: number;
  chunkOverlap?: number;
  separator?: string;
  columnConfig?: ColumnConfigRow[];
  chunkCount?: number;
}

export interface ChunkPreview {
  content: string;
  index: number;
  metadata: {
    source: string;
    start: number;
    end: number;
  };
}

export type WizardStep = 1 | 2;
