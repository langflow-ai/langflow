export type ScorerType =
  | "exact_match"
  | "contains"
  | "similarity"
  | "llm_judge";

export interface JudgeModelSelection {
  name: string;
  provider: string;
  icon?: string;
  metadata?: Record<string, unknown>;
}

export interface ScorerSpec {
  type: ScorerType;
  name: string;
  weight?: number;
  config?: {
    model?: JudgeModelSelection[];
    rubric?: string;
    case_sensitive?: boolean;
    /** LLM judge: most output tokens per row (default 600). */
    max_output_tokens?: number;
    /** LLM judge: most output tokens over the whole run (default 8192). */
    max_run_output_tokens?: number;
    /** LLM judge: stop the run when either limit is reached (default true). */
    stop_on_output_limit?: boolean;
    /** LLM judge: safety checks run on each answer; a flagged one fails the row. */
    safety_checks?: SafetyCheck[];
  };
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export interface Dataset {
  id: string;
  name: string;
  description: string | null;
  revision: number;
  item_count: number;
  created_at: string;
  updated_at: string;
}

export interface DatasetExample {
  key: string;
  name: string;
  description: string;
  item_count: number;
}

export interface DatasetItem {
  id: string;
  position: number;
  input: string;
  expected_output: string | null;
  source: string;
  created_at: string;
  updated_at: string;
}

export interface CsvPreview {
  headers: string[];
  rows: string[][];
  total_rows: number;
}

export interface CsvImportResult {
  imported: number;
  skipped: { row: number; reason: string }[];
}

export type RunStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface ScoreStats {
  mean: number | null;
  p50: number | null;
  p90: number | null;
}

export interface RunSummary {
  scores: Record<string, ScoreStats>;
  duration_ms: ScoreStats;
  tokens: { flow: number; judge: number; total: number };
  cost_usd: {
    flow: number | null;
    judge: number | null;
    total: number | null;
    complete: boolean;
  };
  pass_rate: number | null;
  rows: { total: number; errored: number; decided: number };
  /** Per LLM judge with safety checks; absent on runs from before safety checks. */
  safety?: Record<string, SafetySummary>;
}

export interface RunEstimate {
  items: number;
  basis: "history" | "model";
  llm_calls: number;
  judge_calls: number;
  flow_tokens_low: number;
  flow_tokens_high: number;
  judge_tokens_low: number;
  judge_tokens_high: number;
  tokens_low: number;
  tokens_high: number;
  cost_low: number | null;
  cost_high: number | null;
  unpriced_models: string[];
  has_agent: boolean;
  /** How many runs the figures cover: a comparison runs the dataset once per variant. */
  variants?: number;
}

/** The models of one run in a comparison: the dataset runs once per variant, one after another. */
export interface ModelVariant {
  model_overrides: ModelOverride[];
}

/** Stored on each run of a comparison; `variants` is the whole plan, `index` this run's place in it. */
export interface RunComparison {
  id: string;
  index: number;
  variants: ModelOverride[][];
}

export interface EvaluationRun {
  id: string;
  evaluation_id: string;
  status: RunStatus;
  flow_id: string | null;
  flow_name: string;
  flow_version_id: string | null;
  flow_version_number: number | null;
  flow_version_source: "latest" | "history";
  dataset_id: string | null;
  dataset_name: string;
  dataset_revision: number;
  config: {
    scorers: ScorerSpec[];
    pass_threshold: number;
    output_vertex_id: string;
    model_overrides?: ModelOverride[];
    comparison?: RunComparison;
  };
  total_items: number;
  completed_items: number;
  failed_items: number;
  passed_items: number;
  summary: RunSummary | null;
  estimate: RunEstimate | null;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface Evaluation {
  id: string;
  name: string;
  project_id: string | null;
  flow_id: string | null;
  flow_name: string | null;
  dataset_id: string | null;
  dataset_name: string | null;
  output_vertex_id: string | null;
  scorers: ScorerSpec[];
  pass_threshold: number;
  last_run: EvaluationRun | null;
  created_at: string;
  updated_at: string;
}

export const SAFETY_CHECKS = [
  "off_topic",
  "pii_exposure",
  "prompt_injection",
  "jailbreak",
] as const;
export type SafetyCheck = (typeof SAFETY_CHECKS)[number];
export type InputAttack =
  | "none"
  | "prompt_injection"
  | "jailbreak"
  | "pii_request"
  | "off_topic";

export interface ScoreEntry {
  value: number | null;
  comment?: string;
  /** The LLM judge's safety checks on the answer, when the evaluation asked for them. */
  safety?: Partial<Record<SafetyCheck, boolean>>;
  input_attack?: InputAttack | null;
}

/** Safety rates of one LLM judge over the rows it checked. */
export interface SafetySummary {
  checks: SafetyCheck[];
  judged: number;
  skipped: number;
  safe: number | null;
  rates: Partial<Record<SafetyCheck, number | null>>;
  attacks: { total: number; resisted: number };
}

export interface EvaluationResult {
  id: string;
  position: number;
  input: string;
  expected_output: string | null;
  actual_output: string | null;
  output_truncated: boolean;
  error: string | null;
  scores: Record<string, ScoreEntry>;
  passed: boolean | null;
  duration_ms: number;
  tokens_flow: number | null;
  tokens_judge: number | null;
  cost_flow: number | null;
  cost_judge: number | null;
  trace_id: string | null;
  /** True in the results list when texts are clipped; the single-result read has them in full. */
  preview?: boolean;
}

export interface FlowCheckIssue {
  code: string;
  message: string;
  components: string[];
}

/** A model selection as a model field stores it: one `{ name, provider, ... }` entry. */
export type ModelSelection = {
  name: string;
  provider: string;
  icon?: string;
  metadata?: Record<string, unknown>;
}[];

/** A component's model picker, which a run can point at another model. */
export interface FlowModelPicker {
  node_id: string;
  component: string;
  field: string;
  display_name: string;
  model_type: string;
  value: ModelSelection;
}

/** Runs one model picker with another model, for that run only. */
export interface ModelOverride {
  node_id: string;
  field: string;
  value: ModelSelection;
}

export interface FlowCheckReport {
  blocking: FlowCheckIssue[];
  warnings: FlowCheckIssue[];
  output_vertices: { id: string; name: string }[];
  model_pickers: FlowModelPicker[];
}

export const TERMINAL_RUN_STATUSES: ReadonlySet<RunStatus> = new Set([
  "completed",
  "failed",
  "cancelled",
]);
