import { useMemo, useRef, useState } from "react";
import type { ModelOption } from "@/components/core/parameterRenderComponent/components/modelInputComponent/types";
import type {
  Evaluation,
  EvaluationRun,
  ModelSelection,
  SafetyCheck,
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
import {
  buildModelVariants,
  MAX_MODEL_VARIANTS,
  type ModelVersion,
} from "./modelOverrideUtils";

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
  safetyChecks: readonly SafetyCheck[] = [],
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
        ...(safetyChecks.length > 0 && { safety_checks: [...safetyChecks] }),
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
  const [safetyChecks, setSafetyChecks] = useState<SafetyCheck[]>([]);
  // One entry per model version; two or more run the dataset once each and compare them.
  const nextVersionKey = useRef(1);
  const [modelVersions, setModelVersions] = useState<ModelVersion[]>([
    { key: 0, chosen: {} },
  ]);

  const scorers = useMemo(
    () => buildScorers(selected, judgeModel, rubric, judgeLimits, safetyChecks),
    [selected, judgeModel, rubric, judgeLimits, safetyChecks],
  );
  const check = useCheckFlowForEvaluation({
    flowId,
    outputVertexId: outputVertexId || null,
  });
  const variantOverrides = useMemo(
    () => buildModelVariants(check.data?.model_pickers ?? [], modelVersions),
    [check.data?.model_pickers, modelVersions],
  );
  const comparing = variantOverrides.length > 1;
  const modelOverrides = comparing ? [] : (variantOverrides[0] ?? []);
  const variants = comparing
    ? variantOverrides.map((overrides) => ({ model_overrides: overrides }))
    : [];
  const estimate = useEstimateEvaluation({
    flowId,
    datasetId,
    scorers,
    modelOverrides,
    variants,
  });
  const createEvaluation = useCreateEvaluation();
  const judgeMissingModel = selected.has("llm_judge") && !judgeModel[0];
  const judgeOn = selected.has("llm_judge");
  const rowBudget = parseJudgeMaxTokens(judgeLimits.maxOutputTokens);
  const judgeRowBudgetInvalid = judgeOn && rowBudget === null;
  const judgeRunBudgetInvalid =
    judgeOn &&
    parseJudgeRunMaxTokens(judgeLimits.maxRunOutputTokens, rowBudget) === null;
  const judgeLimitsInvalid = judgeRowBudgetInvalid || judgeRunBudgetInvalid;

  const chooseModel = (
    version: number,
    key: string,
    value: ModelSelection | null,
  ) =>
    setModelVersions((current) =>
      current.map((entry, index) => {
        if (index !== version) return entry;
        const { [key]: _dropped, ...rest } = entry.chosen;
        return { ...entry, chosen: value ? { ...rest, [key]: value } : rest };
      }),
    );

  // A new version starts as a copy of another, so trying one other model is a single pick.
  const duplicateModelVersion = (version: number) =>
    setModelVersions((current) =>
      current.length >= MAX_MODEL_VARIANTS || !current[version]
        ? current
        : [
            ...current.slice(0, version + 1),
            { key: nextVersionKey.current++, chosen: current[version].chosen },
            ...current.slice(version + 1),
          ],
    );

  const removeModelVersion = (version: number) =>
    setModelVersions((current) =>
      current.length <= 1
        ? current
        : current.filter((_, index) => index !== version),
    );

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

  /** Create the evaluation and start its first run (a comparison's first variant), in one atomic request. */
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
        ...(comparing ? { variants } : { model_overrides: modelOverrides }),
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
      modelVersions,
      safetyChecks,
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
      chooseModel,
      duplicateModelVersion,
      removeModelVersion,
      setSafetyChecks,
      resetModels: () => setModelVersions([{ key: 0, chosen: {} }]),
    },
    check,
    estimate,
    comparing,
    canSubmit,
    judgeMissingModel,
    judgeRowBudgetInvalid,
    judgeRunBudgetInvalid,
    createAndRun,
  };
}
