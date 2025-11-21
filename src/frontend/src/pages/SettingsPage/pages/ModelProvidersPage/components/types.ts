export type Model = {
  model_name: string;
  metadata: Record<string, any>;
};

export type Provider = {
  provider: string;
  icon?: string;
  is_enabled: boolean;
  model_count?: number;
  models?: Model[];
};

export type EnabledModelsData = {
  enabled_models?: Record<string, Record<string, boolean>>;
};

export type DefaultModelData = {
  default_model?: {
    model_name: string;
    provider: string;
    model_type: string;
  } | null;
};
