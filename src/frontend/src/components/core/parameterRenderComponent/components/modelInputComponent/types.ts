import type { APIClassType } from "@/types/api";

export interface ModelOption {
  id?: string;
  name: string;
  icon: string;
  provider: string;
  metadata?: Record<string, unknown>;
}

export type ExternalOptionsType = {
  fields: { data: { node: APIClassType } };
  functionality?: string;
};

export type SelectedModel = ModelOption;

export interface ModelInputComponentType {
  options?: ModelOption[];
  placeholder?: string;
  externalOptions?: ExternalOptionsType;
  /** When true and options are empty, shows "No models enabled" in a clickable dropdown instead of loading state */
  showEmptyState?: boolean;
  /** Explicitly set the model type filter ("llm" or "embeddings"). Overrides the nodeClass-derived default. */
  modelType?: "llm" | "embeddings";
}
