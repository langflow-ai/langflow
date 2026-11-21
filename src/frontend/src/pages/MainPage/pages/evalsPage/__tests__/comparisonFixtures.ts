import type {
  EvaluationRun,
  ModelOverride,
  SafetySummary,
} from "@/controllers/API/queries/evals/types";

export const override = (name: string, provider = "OpenAI"): ModelOverride => ({
  node_id: "Agent-1",
  field: "model",
  value: [{ name, provider }],
});

export const PLAN: ModelOverride[][] = [
  [],
  [override("gpt-4o-mini")],
  [override("claude-haiku-5-5", "Anthropic")],
];

interface VariantRun {
  index: number;
  status?: EvaluationRun["status"];
  passed?: number;
  decided?: number;
  cost?: number | null;
  p50?: number | null;
  safety?: SafetySummary;
  finishedAt?: string | null;
  plan?: ModelOverride[][];
}

export function variantRun({
  index,
  status = "completed",
  passed = 8,
  decided = 10,
  cost = 0.01,
  p50 = 1000,
  safety,
  finishedAt = "2026-10-30T11:00:00Z",
  plan = PLAN,
}: VariantRun): EvaluationRun {
  return {
    id: `run-${index}`,
    evaluation_id: "eval-1",
    status,
    flow_id: "flow-1",
    flow_name: "Support",
    flow_version_id: "v-1",
    flow_version_number: 3,
    flow_version_source: "history",
    dataset_id: "ds-1",
    dataset_name: "support-qa",
    dataset_revision: 1,
    config: {
      scorers: [],
      pass_threshold: 0.5,
      output_vertex_id: "out",
      model_overrides: plan[index],
      comparison: { id: "cmp-1", index, variants: plan },
    },
    total_items: decided,
    completed_items: decided,
    failed_items: 0,
    passed_items: passed,
    summary: {
      scores: {},
      duration_ms: { mean: p50, p50, p90: p50 === null ? null : p50 * 2 },
      tokens: { flow: 100, judge: 0, total: 100 },
      cost_usd: {
        flow: cost,
        judge: null,
        total: cost,
        complete: cost !== null,
      },
      pass_rate: decided ? passed / decided : null,
      rows: { total: decided, errored: 0, decided },
      ...(safety && { safety: { judge: safety } }),
    },
    estimate: null,
    error: null,
    started_at: "2026-10-30T10:00:00Z",
    finished_at: status === "running" ? null : finishedAt,
    created_at: `2026-10-30T10:0${index}:00Z`,
  };
}
