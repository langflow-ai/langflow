import { useCallback, useMemo, useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useGenerateDataset } from "@/controllers/API/queries/datasets/use-generate-dataset";
import { useGetLLMModels } from "@/controllers/API/queries/models/use-get-llm-models";
import useAlertStore from "@/stores/alertStore";
import BaseModal from "../baseModal";
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

interface GenerateDatasetModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  onSuccess?: (datasetId: string) => void;
}

export default function GenerateDatasetModal({
  open,
  setOpen,
  onSuccess,
}: GenerateDatasetModalProps): JSX.Element {
  const [name, setName] = useState("");
  const [topic, setTopic] = useState("");
  const [numItems, setNumItems] = useState("10");
  const [selectedModel, setSelectedModel] = useState<{
    name: string;
    provider: string;
    icon: string;
    metadata: Record<string, any>;
  } | null>(null);
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false);
  const [modelProviderModalOpen, setModelProviderModalOpen] = useState(false);
  const modelButtonRef = useRef<HTMLButtonElement>(null);

  const { data: llmModelsData, isLoading: modelsLoading, refetch: refetchModels } = useGetLLMModels({});

  const { setErrorData, setSuccessData } = useAlertStore((state) => ({
    setErrorData: state.setErrorData,
    setSuccessData: state.setSuccessData,
  }));

  const generateDatasetMutation = useGenerateDataset({
    onSuccess: (data) => {
      setSuccessData({ title: "Generating dataset..." });
      setOpen(false);
      resetForm();
      onSuccess?.(data.id);
    },
    onError: (error: any) => {
      setErrorData({
        title: "Failed to generate dataset",
        list: [
          error?.response?.data?.detail ||
            error?.message ||
            "An unknown error occurred",
        ],
      });
    },
  });

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
    setTopic("");
    setNumItems("10");
    setSelectedModel(null);
  };

  const handleSubmit = () => {
    if (!name.trim()) {
      setErrorData({
        title: "Validation error",
        list: ["Dataset name is required"],
      });
      return;
    }

    if (!topic.trim()) {
      setErrorData({
        title: "Validation error",
        list: ["Topic is required"],
      });
      return;
    }

    if (!selectedModel) {
      setErrorData({
        title: "Validation error",
        list: ["Please select a model"],
      });
      return;
    }

    generateDatasetMutation.mutate({
      name: name.trim(),
      topic: topic.trim(),
      num_items: parseInt(numItems, 10) || 10,
      model: {
        name: selectedModel.name,
        provider: selectedModel.provider,
        icon: selectedModel.icon,
        metadata: selectedModel.metadata,
      },
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

  if (!open) return <></>;

  return (
    <>
      <BaseModal
        open={open}
        setOpen={handleClose}
        size="small-h-full"
        onSubmit={handleSubmit}
      >
        <BaseModal.Header description="Use an LLM to generate input/expected_output pairs for your dataset.">
          <ForwardedIconComponent
            name="Sparkles"
            className="mr-2 h-4 w-4"
          />
          Generate Dataset
        </BaseModal.Header>
        <BaseModal.Content className="flex flex-col gap-6 px-6 py-4">
          {/* Name field */}
          <div className="flex flex-col gap-2">
            <Label htmlFor="generate-dataset-name">
              Name <span className="text-destructive">*</span>
            </Label>
            <Input
              id="generate-dataset-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Enter dataset name"
              autoFocus
            />
          </div>

          {/* Topic field */}
          <div className="flex flex-col gap-2">
            <Label htmlFor="generate-dataset-topic">
              Topic <span className="text-destructive">*</span>
            </Label>
            <p className="text-xs text-muted-foreground">
              Describe what kind of data to generate.
            </p>
            <Textarea
              id="generate-dataset-topic"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. Questions about Python programming"
              className="min-h-[100px] text-sm"
            />
          </div>

          {/* Number of items */}
          <div className="flex flex-col gap-2">
            <Label htmlFor="generate-dataset-num-items">
              Number of items
            </Label>
            <Input
              id="generate-dataset-num-items"
              type="number"
              min={1}
              max={500}
              value={numItems}
              onChange={(e) => setNumItems(e.target.value)}
              onBlur={(e) => {
                const val = parseInt(e.target.value, 10);
                if (isNaN(val) || val < 1) {
                  setNumItems("1");
                } else if (val > 500) {
                  setNumItems("500");
                }
              }}
            />
          </div>

          {/* Model picker */}
          <div className="flex flex-col gap-2">
            <Label>
              Model <span className="text-destructive">*</span>
            </Label>
            <Popover open={modelDropdownOpen} onOpenChange={setModelDropdownOpen}>
              {!hasEnabledProviders && !modelsLoading ? (
                <Button
                  variant="default"
                  size="sm"
                  className="w-full"
                  onClick={() => setModelProviderModalOpen(true)}
                >
                  <ForwardedIconComponent name="Brain" className="h-4 w-4" />
                  <div className="text-[13px]">Setup Provider</div>
                </Button>
              ) : (
                <PopoverTrigger asChild>
                  <Button
                    disabled={modelsLoading}
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
                    <Button
                      className="w-full flex cursor-pointer items-center justify-start gap-2 truncate py-2 text-xs text-muted-foreground px-3 hover:bg-accent group"
                      unstyled
                      onClick={() => {
                        setModelDropdownOpen(false);
                        setModelProviderModalOpen(true);
                      }}
                    >
                      <div className="flex items-center gap-2 pl-1 group-hover:text-primary">
                        Manage Model Providers
                        <ForwardedIconComponent
                          name="Settings"
                          className="w-4 h-4 text-muted-foreground group-hover:text-primary"
                        />
                      </div>
                    </Button>
                  </div>
                </Command>
              </PopoverContent>
            </Popover>
          </div>
        </BaseModal.Content>
        <BaseModal.Footer
          submit={{
            label: "Generate",
            loading: generateDatasetMutation.isPending,
            disabled:
              !name.trim() ||
              !topic.trim() ||
              !selectedModel ||
              generateDatasetMutation.isPending,
            dataTestId: "btn-generate-dataset",
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
