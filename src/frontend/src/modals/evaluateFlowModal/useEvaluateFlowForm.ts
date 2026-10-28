import { useMemo, useState } from "react";
import type { ModelOption } from "@/components/core/parameterRenderComponent/components/modelInputComponent/types";
import type {
  Evaluation,
  EvaluationRun,
  ScorerSpec,
  ScorerType,
} from "@/controllers/API/queries/evals/types";
import {
  type EvaluationCreatePayload,
  useCheckFlowForEvaluation,
  useCreateEvaluation,
  useEstimateEvaluation,
} from "@/controllers/API/queries/evals/use-evaluations";
import type { JudgeLimits } from "./JudgeLimitFields";
import {
  DEFAULT_JUDGE_MAX_OUTPUT_TOKENS,
  DEFAULT_JUDGE_MAX_RUN_OUTPUT_TOKENS,
  parseJudgeMaxTokens,
  parseJudgeRunMaxTokens,
} from "./judgeLimits";

export const LATEST_VERSION = "latest";
export const TEXT_SCORERS: ScorerType[] = [
  "exact_match",
  "contains",
  "similarity",
];
const DEFAULT_THRESHOLD = 0.5;
const DEFAULT_JUDGE_LIMITS: JudgeLimits = {
  maxOutputTokens: String(DEFAULT_JUDGE_MAX_OUTPUT_TOKENS),
  maxRunOutputTokens: String(DEFAULT_JUDGE_MAX_RUN_OUTPUT_TOKENS),
  stopOnOutputLimit: true,
};

export function buildScorers(
  selected: ReadonlySet<ScorerType>,
  judgeModel: ModelOption[],
  rubric: string,
  judgeLimits: JudgeLimits = DEFAULT_JUDGE_LIMITS,
): ScorerSpec[] {
  const scorers: ScorerSpec[] = TEXT_SCORERS.filter((type) =>
    selected.has(type),
  ).map((type) => ({ type, name: type }));
  if (selected.has("llm_judge") && judgeModel[0]) {
    const model = judgeModel[0];
    const rowBudget = parseJudgeMaxTokens(judgeLimits.maxOutputTokens);
    scorers.push({
      type: "llm_judge",
      name: "llm_judge",
      config: {
        model: [
          {
            name: model.name,
            provider: model.provider,
            icon: model.icon,
            metadata: model.metadata,
          },
        ],
        rubric: rubric.trim() || undefined,
        max_output_tokens: rowBudget ?? DEFAULT_JUDGE_MAX_OUTPUT_TOKENS,
        max_run_output_tokens:
          parseJudgeRunMaxTokens(judgeLimits.maxRunOutputTokens, rowBudget) ??
          DEFAULT_JUDGE_MAX_RUN_OUTPUT_TOKENS,
        stop_on_output_limit: judgeLimits.stopOnOutputLimit,
      },
    });
  }
  return scorers;
}

function isRun(created: Evaluation | EvaluationRun): created is EvaluationRun {
  return "evaluation_id" in created;
}

export function useEvaluateFlowForm(flowId: string) {
  const [name, setName] = useState("");
  const [datasetId, setDatasetId] = useState("");
  const [versionId, setVersionId] = useState(LATEST_VERSION);
  const [outputVertexId, setOutputVertexId] = useState("");
  const [selected, setSelected] = useState<Set<ScorerType>>(
    () => new Set<ScorerType>(["exact_match"]),
  );
  const [judgeModel, setJudgeModel] = useState<ModelOption[]>([]);
  const [rubric, setRubric] = useState("");
  const [judgeLimits, setJudgeLimits] =
    useState<JudgeLimits>(DEFAULT_JUDGE_LIMITS);
  const [threshold, setThreshold] = useState(DEFAULT_THRESHOLD);

  const scorers = useMemo(
    () => buildScorers(selected, judgeModel, rubric, judgeLimits),
    [selected, judgeModel, rubric, judgeLimits],
  );
  const check = useCheckFlowForEvaluation({
    flowId,
    outputVertexId: outputVertexId || null,
  });
  const estimate = useEstimateEvaluation({ flowId, datasetId, scorers });
  const createEvaluation = useCreateEvaluation();
  const judgeMissingModel = selected.has("llm_judge") && !judgeModel[0];
  const judgeOn = selected.has("llm_judge");
  const rowBudget = parseJudgeMaxTokens(judgeLimits.maxOutputTokens);
  const judgeRowBudgetInvalid = judgeOn && rowBudget === null;
  const judgeRunBudgetInvalid =
    judgeOn &&
    parseJudgeRunMaxTokens(judgeLimits.maxRunOutputTokens, rowBudget) === null;
  const judgeLimitsInvalid = judgeRowBudgetInvalid || judgeRunBudgetInvalid;

  const toggleScorer = (type: ScorerType, on: boolean) =>
    setSelected((current) => {
      const next = new Set(current);
      if (on) next.add(type);
      else next.delete(type);
      return next;
    });

  const canSubmit =
    Boolean(flowId) &&
    Boolean(datasetId) &&
    scorers.length > 0 &&
    !judgeMissingModel &&
    !judgeLimitsInvalid &&
    (check.data?.blocking.length ?? 1) === 0;

  /** Create the evaluation and start its first run on the chosen version, in one atomic request. */
  const createAndRun = async (): Promise<EvaluationRun> => {
    const payload: EvaluationCreatePayload = {
      flow_id: flowId,
      dataset_id: datasetId,
      name: name.trim() || undefined,
      output_vertex_id: outputVertexId || null,
      scorers,
      pass_threshold: threshold,
    };
    const started = await createEvaluation.mutateAsync({
      payload: {
        ...payload,
        flow_version_id: versionId === LATEST_VERSION ? null : versionId,
      },
      run: true,
    });
    if (!isRun(started)) throw new Error("The server did not start a run.");
    return started;
  };

  return {
    state: {
      name,
      datasetId,
      versionId,
      outputVertexId,
      selected,
      judgeModel,
      rubric,
      judgeLimits,
      threshold,
    },
    set: {
      setName,
      setDatasetId,
      setVersionId,
      setOutputVertexId,
      toggleScorer,
      setJudgeModel,
      setRubric,
      setJudgeLimits,
      setThreshold,
    },
    check,
    estimate,
    canSubmit,
    judgeMissingModel,
    judgeRowBudgetInvalid,
    judgeRunBudgetInvalid,
    createAndRun,
  };
}
