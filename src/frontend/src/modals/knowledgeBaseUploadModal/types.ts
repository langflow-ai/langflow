import type { ModelOption } from "@/components/core/parameterRenderComponent/components/modelInputComponent";

export interface KnowledgeBaseUploadModalProps {
  open?: boolean;
  setOpen?: (open: boolean) => void;
  onSubmit?: (data: KnowledgeBaseFormData) => void;
  existingKnowledgeBase?: {
    name: string;
    embeddingProvider?: string;
    embeddingModel?: string;
  };
}

export interface KnowledgeBaseFormData {
  sourceName: string;
  files: File[];
  embeddingModel: ModelOption[] | null;
  chunkSize: number;
  chunkOverlap: number;
  separator: string;
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
