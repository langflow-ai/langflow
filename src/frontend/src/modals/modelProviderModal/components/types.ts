/** Represents a single AI model (LLM or embedding) */
export type Model = {
  model_name: string;
  /** Arbitrary metadata including icon, model_type, deprecated, default flags */
  metadata: Record<string, any>;
};

/** Represents a model provider (e.g., OpenAI, Anthropic) */
export type Provider = {
  provider: string;
  icon?: string;
  is_enabled: boolean;
  model_count?: number;
  models?: Model[];
  api_docs_url?: string;
};

/** Map of provider -> model_name -> enabled status */
export type EnabledModelsData = {
  enabled_models?: Record<string, Record<string, boolean>>;
};

/** Currently selected default model configuration */
export type DefaultModelData = {
  default_model?: {
    model_name: string;
    provider: string;
    model_type: string;
  } | null;
};
