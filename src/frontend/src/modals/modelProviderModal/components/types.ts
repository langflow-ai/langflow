/** Represents a single AI model (LLM or embedding) */
export type Model = {
  model_name: string;
  /** Arbitrary metadata including icon, model_type, deprecated, default flags */
  metadata: Record<string, any>;
};

/** A provider variable as exposed in the ``/api/v1/models`` payload. The
 * shape mirrors ``MODEL_PROVIDER_METADATA[<provider>].variables`` on the
 * backend; only the fields the frontend actually reads are listed.
 */
export type ProviderVariableInfo = {
  variable_name?: string;
  variable_key?: string;
  required?: boolean;
  is_secret?: boolean;
};

/** Represents a model provider (e.g., OpenAI, Anthropic) */
export type Provider = {
  provider: string;
  icon?: string;
  is_enabled: boolean;
  is_configured?: boolean;
  model_count?: number;
  models?: Model[];
  api_docs_url?: string;
  variables?: ProviderVariableInfo[];
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
