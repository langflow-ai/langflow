import { useCallback, useMemo, useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useGetDatasets } from "@/controllers/API/queries/datasets/use-get-datasets";
import { useCreateEvaluation } from "@/controllers/API/queries/evaluations/use-create-evaluation";
import { useGetLLMModels } from "@/controllers/API/queries/models/use-get-llm-models";
import useAlertStore from "@/stores/alertStore";
import BaseModal from "../baseModal";
import MultiselectComponent from "@/components/core/parameterRenderComponent/components/multiselectComponent";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandGroup,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/utils/utils";
import ModelProviderModal from "@/modals/modelProviderModal";

interface CreateEvaluationModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  flowId: string;
  flowName: string;
  onSuccess?: (evaluationId: string) => void;
}

const SCORING_METHOD_OPTIONS = [
  "exact_match",
  "contains",
  "similarity",
  "llm_judge",
];

const DEFAULT_LLM_JUDGE_PROMPT = `Rate how well the actual output matches the expected output on a scale from 0 to 1. Consider accuracy, completeness, and relevance. Return ONLY a decimal number between 0 and 1, nothing else.`;

export default function CreateEvaluationModal({
  open,
  setOpen,
  flowId,
  flowName,
  onSuccess,
}: CreateEvaluationModalProps): JSX.Element {
  const [name, setName] = useState("");
  const [datasetId, setDatasetId] = useState("");
  const [scoringMethods, setScoringMethods] = useState<string[]>([
    "exact_match",
  ]);
  const [llmJudgePrompt, setLlmJudgePrompt] = useState(DEFAULT_LLM_JUDGE_PROMPT);
  const [selectedModel, setSelectedModel] = useState<{
    name: string;
    provider: string;
    icon: string;
    metadata: Record<string, any>;
  } | null>(null);
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false);
  const [modelProviderModalOpen, setModelProviderModalOpen] = useState(false);
  const modelButtonRef = useRef<HTMLButtonElement>(null);

  const { data: datasets, isLoading: datasetsLoading } = useGetDatasets();
  const { data: llmModelsData, isLoading: modelsLoading, refetch: refetchModels } = useGetLLMModels({});

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

  // Group models by provider
  const groupedModels = useMemo(() => {
    if (!llmModelsData?.models) return {};
    const grouped: Record<string, typeof llmModelsData.models> = {};
    for (const model of llmModelsData.models) {
      (grouped[model.provider] ??= []).push(model);
    }
    return grouped;
  }, [llmModelsData]);

  const hasEnabledProviders = (llmModelsData?.enabledProviders?.length ?? 0) > 0;

  const resetForm = () => {
    setName("");
    setDatasetId("");
    setScoringMethods(["exact_match"]);
    setLlmJudgePrompt(DEFAULT_LLM_JUDGE_PROMPT);
    setSelectedModel(null);
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

    if (scoringMethods.includes("llm_judge") && !llmJudgePrompt.trim()) {
      setErrorData({
        title: "Validation error",
        list: ["Please provide a prompt for the LLM Judge"],
      });
      return;
    }

    if (scoringMethods.includes("llm_judge") && !selectedModel) {
      setErrorData({
        title: "Validation error",
        list: ["Please select a model for the LLM Judge"],
      });
      return;
    }

    createEvaluationMutation.mutate({
      name: name.trim() || undefined,
      dataset_id: datasetId,
      flow_id: flowId,
      scoring_methods: scoringMethods,
      llm_judge_prompt: scoringMethods.includes("llm_judge")
        ? llmJudgePrompt
        : undefined,
      llm_judge_model:
        scoringMethods.includes("llm_judge") && selectedModel
          ? {
              name: selectedModel.name,
              provider: selectedModel.provider,
              icon: selectedModel.icon,
              metadata: selectedModel.metadata,
            }
          : undefined,
      run_immediately: true,
    });
  };

  const handleClose = () => {
    setOpen(false);
    resetForm();
  };

  const handleModelSelect = useCallback(
    (model: (typeof llmModelsData.models)[0]) => {
      setSelectedModel(model);
      setModelDropdownOpen(false);
    },
    [],
  );

  const showLlmJudgeFields = scoringMethods.includes("llm_judge");

  if (!open) return <></>;

  return (
    <>
      <BaseModal
        open={open}
        setOpen={handleClose}
        size="small-h-full"
        onSubmit={handleSubmit}
      >
        <BaseModal.Header
          description={`Evaluate "${flowName}" against a dataset`}
        >
          <ForwardedIconComponent
            name="FlaskConical"
            className="mr-2 h-4 w-4"
          />
          Create Evaluation
        </BaseModal.Header>
        <BaseModal.Content className="flex flex-col gap-6 px-6 py-4">
          {/* Name field */}
          <div className="flex flex-col gap-2">
            <Label htmlFor="evaluation-name">Name (optional)</Label>
            <Input
              id="evaluation-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Auto-generated if empty"
            />
          </div>

          {/* Dataset selector */}
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

          {/* Scoring Methods */}
          <div className="flex flex-col gap-2">
            <Label>
              Scoring Methods <span className="text-destructive">*</span>
            </Label>
            <MultiselectComponent
              id="scoring-methods"
              value={scoringMethods}
              options={SCORING_METHOD_OPTIONS}
              handleOnNewValue={({ value }) => setScoringMethods(value)}
              disabled={false}
              editNode={false}
            />
          </div>

          {/* LLM Judge Model - styled like Language Model component */}
          <div
            className={cn(
              "flex flex-col gap-2",
              !showLlmJudgeFields && "opacity-40 pointer-events-none",
            )}
          >
            <Label>
              LLM Judge Model{" "}
              {showLlmJudgeFields && (
                <span className="text-destructive">*</span>
              )}
            </Label>
            <Popover open={modelDropdownOpen} onOpenChange={setModelDropdownOpen}>
              {!hasEnabledProviders && !modelsLoading ? (
                <Button
                  variant="default"
                  size="sm"
                  className="w-full"
                  onClick={() => setModelProviderModalOpen(true)}
                  disabled={!showLlmJudgeFields}
                >
                  <ForwardedIconComponent name="Brain" className="h-4 w-4" />
                  <div className="text-[13px]">Setup Provider</div>
                </Button>
              ) : (
                <PopoverTrigger asChild>
                  <Button
                    disabled={!showLlmJudgeFields || modelsLoading}
                    variant="primary"
                    size="xs"
                    role="combobox"
                    ref={modelButtonRef}
                    aria-expanded={modelDropdownOpen}
                    className={cn(
                      "dropdown-component-false-outline py-2",
                      "w-full justify-between font-normal",
                    )}
                  >
                    <span className="flex w-full items-center gap-2 overflow-hidden">
                      {selectedModel && (
                        <ForwardedIconComponent
                          name={selectedModel.icon || "Bot"}
                          className="h-4 w-4 flex-shrink-0"
                        />
                      )}
                      <span
                        className={cn(
                          "truncate",
                          !selectedModel && "text-muted-foreground",
                        )}
                      >
                        {selectedModel?.name || "Select a model"}
                      </span>
                    </span>
                    <ForwardedIconComponent
                      name="ChevronsUpDown"
                      className="ml-2 h-4 w-4 shrink-0 text-foreground"
                    />
                  </Button>
                </PopoverTrigger>
              )}
              <PopoverContent
                side="bottom"
                avoidCollisions={true}
                className="p-0"
                style={{
                  minWidth: modelButtonRef?.current?.clientWidth ?? "200px",
                }}
              >
                <Command className="flex flex-col">
                  <CommandList className="max-h-[300px] overflow-y-auto">
                    {Object.entries(groupedModels).map(([provider, models]) => (
                      <CommandGroup className="p-0" key={provider}>
                        <div className="text-xs font-semibold my-2 ml-4 text-muted-foreground">
                          {provider}
                        </div>
                        {models.map((model) => (
                          <CommandItem
                            key={`${model.provider}::${model.name}`}
                            value={model.name}
                            onSelect={() => handleModelSelect(model)}
                            className="w-full items-center rounded-none"
                          >
                            <div className="flex w-full items-center gap-2">
                              <ForwardedIconComponent
                                name={model.icon || "Bot"}
                                className="h-4 w-4 shrink-0 text-primary ml-2"
                              />
                              <div className="truncate text-[13px]">
                                {model.name}
                              </div>
                              <div className="pl-2 ml-auto">
                                <ForwardedIconComponent
                                  name="Check"
                                  className={cn(
                                    "h-4 w-4 shrink-0 text-primary",
                                    selectedModel?.name === model.name &&
                                      selectedModel?.provider === model.provider
                                      ? "opacity-100"
                                      : "opacity-0",
                                  )}
                                />
                              </div>
                            </div>
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    ))}
                  </CommandList>
                  <div className="border-t bg-background">
                    <CommandItem
                      value="__manage_providers__"
                      onSelect={() => {
                        setModelDropdownOpen(false);
                        setModelProviderModalOpen(true);
                      }}
                      className="cursor-pointer rounded-none px-3 py-2 text-xs text-muted-foreground aria-selected:bg-accent group"
                    >
                      <div className="flex items-center gap-2 pl-1 group-hover:text-primary group-aria-selected:text-primary">
                        Manage Model Providers
                        <ForwardedIconComponent
                          name="Settings"
                          className="w-4 h-4 text-muted-foreground group-hover:text-primary group-aria-selected:text-primary"
                        />
                      </div>
                    </CommandItem>
                  </div>
                </Command>
              </PopoverContent>
            </Popover>
          </div>

          {/* LLM Judge Instructions */}
          <div
            className={cn(
              "flex flex-col gap-2",
              !showLlmJudgeFields && "opacity-40 pointer-events-none",
            )}
          >
            <Label htmlFor="llm-judge-prompt">
              LLM Judge Instructions{" "}
              {showLlmJudgeFields && (
                <span className="text-destructive">*</span>
              )}
            </Label>
            <p className="text-xs text-muted-foreground">
              Instructions for the LLM to evaluate responses.
            </p>
            <Textarea
              id="llm-judge-prompt"
              value={llmJudgePrompt}
              onChange={(e) => setLlmJudgePrompt(e.target.value)}
              placeholder="Describe how to score the response (0-1)..."
              className="min-h-[120px] text-sm"
              disabled={!showLlmJudgeFields}
            />
          </div>
        </BaseModal.Content>
        <BaseModal.Footer
          submit={{
            label: "Run",
            loading: createEvaluationMutation.isPending,
            disabled:
              !datasetId ||
              scoringMethods.length === 0 ||
              (showLlmJudgeFields && !llmJudgePrompt.trim()) ||
              (showLlmJudgeFields && !selectedModel) ||
              createEvaluationMutation.isPending,
            dataTestId: "btn-create-evaluation",
          }}
        />
      </BaseModal>

      {modelProviderModalOpen && (
        <ModelProviderModal
          open={modelProviderModalOpen}
          onClose={() => {
            setModelProviderModalOpen(false);
            refetchModels();
          }}
          modelType="llm"
        />
      )}
    </>
  );
}
