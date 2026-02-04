import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useGetDatasets } from "@/controllers/API/queries/datasets/use-get-datasets";
import { useCreateEvaluation } from "@/controllers/API/queries/evaluations/use-create-evaluation";
import useAlertStore from "@/stores/alertStore";
import BaseModal from "../baseModal";
import { Badge } from "@/components/ui/badge";
import { X } from "lucide-react";

interface CreateEvaluationModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  flowId: string;
  flowName: string;
  onSuccess?: (evaluationId: string) => void;
}

const SCORING_METHODS = [
  { value: "exact_match", label: "Exact Match" },
  { value: "contains", label: "Contains" },
  { value: "similarity", label: "Similarity" },
  { value: "llm_judge", label: "LLM Judge" },
];

export default function CreateEvaluationModal({
  open,
  setOpen,
  flowId,
  flowName,
  onSuccess,
}: CreateEvaluationModalProps): JSX.Element {
  const [name, setName] = useState("");
  const [datasetId, setDatasetId] = useState("");
  const [scoringMethods, setScoringMethods] = useState<string[]>(["exact_match"]);

  const { data: datasets, isLoading: datasetsLoading } = useGetDatasets();

  const { setErrorData, setSuccessData } = useAlertStore((state) => ({
    setErrorData: state.setErrorData,
    setSuccessData: state.setSuccessData,
  }));

  const createEvaluationMutation = useCreateEvaluation({
    onSuccess: (data) => {
      setSuccessData({ title: "Evaluation created successfully" });
      setOpen(false);
      resetForm();
      onSuccess?.(data.id);
    },
    onError: (error: any) => {
      setErrorData({
        title: "Failed to create evaluation",
        list: [
          error?.response?.data?.detail ||
            error?.message ||
            "An unknown error occurred",
        ],
      });
    },
  });

  const resetForm = () => {
    setName("");
    setDatasetId("");
    setScoringMethods(["exact_match"]);
  };

  const handleSubmit = () => {
    if (!datasetId) {
      setErrorData({
        title: "Validation error",
        list: ["Please select a dataset"],
      });
      return;
    }

    if (scoringMethods.length === 0) {
      setErrorData({
        title: "Validation error",
        list: ["Please select at least one scoring method"],
      });
      return;
    }

    createEvaluationMutation.mutate({
      name: name.trim() || undefined,
      dataset_id: datasetId,
      flow_id: flowId,
      scoring_methods: scoringMethods,
      run_immediately: true,
    });
  };

  const handleClose = () => {
    setOpen(false);
    resetForm();
  };

  const toggleScoringMethod = (method: string) => {
    setScoringMethods((prev) =>
      prev.includes(method)
        ? prev.filter((m) => m !== method)
        : [...prev, method],
    );
  };

  if (!open) return <></>;

  return (
    <BaseModal
      open={open}
      setOpen={handleClose}
      size="small-update"
      onSubmit={handleSubmit}
    >
      <BaseModal.Header description={`Evaluate "${flowName}" against a dataset`}>
        Create Evaluation
      </BaseModal.Header>
      <BaseModal.Content className="flex flex-col gap-4 p-4">
        <div className="flex flex-col gap-2">
          <Label htmlFor="evaluation-name">Name (optional)</Label>
          <Input
            id="evaluation-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Auto-generated if empty"
          />
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor="dataset-select">
            Dataset <span className="text-destructive">*</span>
          </Label>
          <Select value={datasetId} onValueChange={setDatasetId}>
            <SelectTrigger id="dataset-select">
              <SelectValue placeholder="Select a dataset" />
            </SelectTrigger>
            <SelectContent>
              {datasetsLoading ? (
                <SelectItem value="loading" disabled>
                  Loading datasets...
                </SelectItem>
              ) : datasets && datasets.length > 0 ? (
                datasets.map((dataset) => (
                  <SelectItem key={dataset.id} value={dataset.id}>
                    {dataset.name} ({dataset.item_count} items)
                  </SelectItem>
                ))
              ) : (
                <SelectItem value="none" disabled>
                  No datasets available
                </SelectItem>
              )}
            </SelectContent>
          </Select>
        </div>

        <div className="flex flex-col gap-2">
          <Label>
            Scoring Methods <span className="text-destructive">*</span>
          </Label>
          <div className="flex flex-wrap gap-2">
            {SCORING_METHODS.map((method) => (
              <Badge
                key={method.value}
                variant={
                  scoringMethods.includes(method.value) ? "default" : "outline"
                }
                className="cursor-pointer"
                onClick={() => toggleScoringMethod(method.value)}
              >
                {method.label}
                {scoringMethods.includes(method.value) && (
                  <X className="ml-1 h-3 w-3" />
                )}
              </Badge>
            ))}
          </div>
        </div>
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: "Create And Run",
          loading: createEvaluationMutation.isPending,
          disabled:
            !datasetId ||
            scoringMethods.length === 0 ||
            createEvaluationMutation.isPending,
          dataTestId: "btn-create-evaluation",
        }}
      />
    </BaseModal>
  );
}
