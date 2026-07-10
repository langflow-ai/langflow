export type TritonServerType = {
  id: string;
  user_id: string;
  name: string;
  base_url: string;
  notes: string | null;
  has_auth_token: boolean;
  created_at: string;
  updated_at: string;
};

export type TritonServerCreateType = {
  name: string;
  base_url: string;
  auth_token?: string | null;
  notes?: string | null;
};

export type TritonServerUpdateType = {
  name?: string;
  base_url?: string;
  auth_token?: string | null;
  notes?: string | null;
};

export type TritonServerCredentialsType = {
  auth_token: string | null;
};

export type TritonServerConnection = {
  base_url: string;
  auth_token?: string | null;
};

export type TritonServerMetadata = {
  name?: string;
  version?: string;
  extensions?: string[];
};

export type TritonModelState =
  | "UNKNOWN"
  | "READY"
  | "UNAVAILABLE"
  | "LOADING"
  | "UNLOADING";

export type TritonModel = {
  name: string;
  state: TritonModelState;
  reason?: string;
};

export type TritonModelListResponse = {
  models?: TritonModel[];
};

export type TritonTensorSpec = {
  name: string;
  data_type: string;
  shape: number[];
  dims?: number[];
  reshape?: { shape: number[] };
  optional?: boolean;
  allow_rag_batch?: boolean;
  rags?: { shape: number[] }[];
};

export type TritonModelConfigResponse = {
  name: string;
  platform: string;
  inputs?: TritonTensorSpec[];
  outputs?: TritonTensorSpec[];
  max_batch_size?: number;
  batcher?: {
    max_batch_size?: number;
    [k: string]: unknown;
  };
  parameters?: Record<string, { string_value?: string; int64_value?: string }>;
  [k: string]: unknown;
};

export type TritonRepositoryState = "UNKNOWN" | "READY" | "UNAVAILABLE";

export type TritonRepositoryIndexEntry = {
  name: string;
  state: TritonRepositoryState;
  reason: string;
};

export type TritonInferInput = {
  name: string;
  shape: number[];
  data: unknown[];
  datatype: string;
  parameters?: Record<string, unknown>;
};

export type TritonInferOutputRequest = {
  name: string;
  parameters?: Record<string, unknown>;
  classification?: number;
};

export type TritonInferRequest = {
  inputs: TritonInferInput[];
  outputs?: TritonInferOutputRequest[];
  parameters?: Record<string, unknown>;
};

export type TritonInferOutput = {
  name: string;
  datatype: string;
  shape: number[];
  data: unknown[];
  parameters?: Record<string, unknown>;
};

export type TritonInferResponse = {
  model_name: string;
  model_version: string;
  outputs: TritonInferOutput[];
  parameters?: Record<string, unknown>;
};

export type TritonDurationStat = {
  count: number;
  ns: number;
};

export type TritonInferenceStats = {
  success?: TritonDurationStat;
  fail?: TritonDurationStat;
  queue?: TritonDurationStat;
  compute_input?: TritonDurationStat;
  compute_infer?: TritonDurationStat;
  compute_output?: TritonDurationStat;
  cache_hit?: TritonDurationStat;
  cache_miss?: TritonDurationStat;
};

export type TritonModelStat = {
  name: string;
  version?: string;
  last_inference?: number;
  inference_count?: number;
  execution_count?: number;
  inference_stats?: TritonInferenceStats;
  response_stats?: Record<string, unknown>;
  batch_stats?: unknown[];
  memory_usage?: unknown[];
  [k: string]: unknown;
};

export type TritonMetricsResponse = {
  model_stats: TritonModelStat[];
};
