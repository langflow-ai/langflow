import { useMemo, useState } from "react";
import type { ModelOption } from "@/components/core/parameterRenderComponent/components/modelInputComponent/types";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import type {
  EvaluationRun,
  ScorerSpec,
  ScorerType,
} from "@/controllers/API/queries/evals/types";
import {
  useCheckFlowForEvaluation,
  useCreateEvaluation,
  useEstimateEvaluation,
} from "@/controllers/API/queries/evals/use-evaluations";

export const LATEST_VERSION = "latest";
export const TEXT_SCORERS: ScorerType[] = [
  "exact_match",
  "contains",
  "similarity",
];
const DEFAULT_THRESHOLD = 0.5;

export function buildScorers(
  selected: ReadonlySet<ScorerType>,
  judgeModel: ModelOption[],
  rubric: string,
): ScorerSpec[] {
  const scorers: ScorerSpec[] = TEXT_SCORERS.filter((type) =>
    selected.has(type),
  ).map((type) => ({ type, name: type }));
  if (selected.has("llm_judge") && judgeModel[0]) {
    const model = judgeModel[0];
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
      },
    });
  }
  return scorers;
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
  const [threshold, setThreshold] = useState(DEFAULT_THRESHOLD);

  const scorers = useMemo(
    () => buildScorers(selected, judgeModel, rubric),
    [selected, judgeModel, rubric],
  );
  const check = useCheckFlowForEvaluation({
    flowId,
    outputVertexId: outputVertexId || null,
  });
  const estimate = useEstimateEvaluation({ flowId, datasetId, scorers });
  const createEvaluation = useCreateEvaluation();
  const judgeMissingModel = selected.has("llm_judge") && !judgeModel[0];

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
    (check.data?.blocking.length ?? 1) === 0;

  /** Create the evaluation, then start its first run on the chosen version. */
  const createAndRun = async (): Promise<EvaluationRun> => {
    const evaluation = await createEvaluation.mutateAsync({
      payload: {
        flow_id: flowId,
        dataset_id: datasetId,
        name: name.trim() || undefined,
        output_vertex_id: outputVertexId || null,
        scorers,
        pass_threshold: threshold,
      },
      run: false,
    });
    const response = await api.post<EvaluationRun>(
      `${getURL("EVALUATIONS")}/${evaluation.id}/runs`,
      { flow_version_id: versionId === LATEST_VERSION ? null : versionId },
    );
    return response.data;
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
      setThreshold,
    },
    check,
    estimate,
    canSubmit,
    judgeMissingModel,
    createAndRun,
  };
}
