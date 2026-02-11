import { useCallback, useMemo, useRef, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
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
import { useGetEmbeddingModels } from "@/controllers/API/queries/models/use-get-embedding-models";
import type { EmbeddingModelsResponse } from "@/controllers/API/queries/models/use-get-embedding-models";
import { useGetLLMModels } from "@/controllers/API/queries/models/use-get-llm-models";
import { useCreateMemory } from "@/controllers/API/queries/memories/use-create-memory";
import useAlertStore from "@/stores/alertStore";
import { cn } from "@/utils/utils";
import BaseModal from "../baseModal";
import ModelProviderModal from "@/modals/modelProviderModal";

interface CreateMemoryModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  flowId: string;
  flowName: string;
  onSuccess?: (memoryId: string) => void;
}

export default function CreateMemoryModal({
  open,
  setOpen,
  flowId,
  flowName,
  onSuccess,
}: CreateMemoryModalProps): JSX.Element {
  const [name, setName] = useState("");
  const [selectedModel, setSelectedModel] = useState<{
    name: string;
    provider: string;
    icon: string;
    metadata: Record<string, any>;
  } | null>(null);
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false);
  const [modelProviderModalOpen, setModelProviderModalOpen] = useState(false);
  const modelButtonRef = useRef<HTMLButtonElement>(null);

  // Batch & preprocessing state
  const [batchSizeInput, setBatchSizeInput] = useState("1");
  const [preprocessingEnabled, setPreprocessingEnabled] = useState(false);
  const [selectedLLMModel, setSelectedLLMModel] = useState<{
    name: string;
    provider: string;
    icon: string;
    metadata: Record<string, any>;
  } | null>(null);
  const [llmModelDropdownOpen, setLlmModelDropdownOpen] = useState(false);
  const [preprocessingPrompt, setPreprocessingPrompt] = useState("");
  const llmModelButtonRef = useRef<HTMLButtonElement>(null);

  const {
    data: embeddingModelsData,
    isLoading: modelsLoading,
    refetch: refetchModels,
  } = useGetEmbeddingModels({});

  const {
    data: llmModelsData,
    isLoading: llmModelsLoading,
    refetch: refetchLLMModels,
  } = useGetLLMModels({});

  const { setErrorData, setSuccessData } = useAlertStore((state) => ({
    setErrorData: state.setErrorData,
    setSuccessData: state.setSuccessData,
  }));

  const createMemoryMutation = useCreateMemory({
    onSuccess: (data) => {
      setSuccessData({ title: "Memory created successfully" });
      setOpen(false);
      resetForm();
      onSuccess?.(data.id);
    },
    onError: (error: any) => {
      setErrorData({
        title: "Failed to create memory",
        list: [
          error?.response?.data?.detail ||
            error?.message ||
            "An unknown error occurred",
        ],
      });
    },
  });

  // Group embedding models by provider
  const groupedModels = useMemo(() => {
    if (!embeddingModelsData?.models) return {};
    const grouped: Record<string, typeof embeddingModelsData.models> = {};
    for (const model of embeddingModelsData.models) {
      (grouped[model.provider] ??= []).push(model);
    }
    return grouped;
  }, [embeddingModelsData]);

  // Group LLM models by provider
  const groupedLLMModels = useMemo(() => {
    if (!llmModelsData?.models) return {};
    const grouped: Record<string, typeof llmModelsData.models> = {};
    for (const model of llmModelsData.models) {
      (grouped[model.provider] ??= []).push(model);
    }
    return grouped;
  }, [llmModelsData]);

  const hasEnabledProviders =
    (embeddingModelsData?.enabledProviders?.length ?? 0) > 0;

  const hasLLMProviders =
    (llmModelsData?.enabledProviders?.length ?? 0) > 0;

  const resetForm = () => {
    setName("");
    setSelectedModel(null);
    setBatchSizeInput("1");
    setPreprocessingEnabled(false);
    setSelectedLLMModel(null);
    setPreprocessingPrompt("");
  };

  const handleModelSelect = useCallback(
    (model: (typeof embeddingModelsData.models)[0]) => {
      setSelectedModel(model);
      setModelDropdownOpen(false);
    },
    [],
  );

  const handleLLMModelSelect = useCallback(
    (model: (typeof llmModelsData.models)[0]) => {
      setSelectedLLMModel(model);
      setLlmModelDropdownOpen(false);
    },
    [],
  );

  const handleSubmit = () => {
    if (!name.trim()) {
      setErrorData({
        title: "Validation error",
        list: ["Please provide a name for the memory"],
      });
      return;
    }

    if (!selectedModel) {
      setErrorData({
        title: "Validation error",
        list: ["Please select an embedding model"],
      });
      return;
    }

    if (preprocessingEnabled && !selectedLLMModel) {
      setErrorData({
        title: "Validation error",
        list: ["Please select an LLM model for preprocessing"],
      });
      return;
    }

    const parsedBatchSize = Math.max(1, parseInt(batchSizeInput, 10) || 1);

    createMemoryMutation.mutate({
      name: name.trim(),
      flow_id: flowId,
      embedding_model: selectedModel.name,
      embedding_provider: selectedModel.provider,
      is_active: true,
      batch_size: parsedBatchSize,
      preprocessing_enabled: preprocessingEnabled,
      preprocessing_model: selectedLLMModel
        ? JSON.stringify(selectedLLMModel)
        : undefined,
      preprocessing_prompt: preprocessingPrompt.trim() || undefined,
    });
  };

  const handleClose = () => {
    setOpen(false);
    resetForm();
  };

  if (!open) return <></>;

  return (
    <>
      <BaseModal
        open={open}
        setOpen={handleClose}
        size="small-h-full"
        onSubmit={handleSubmit}
      >
        <BaseModal.Header description={`Create a memory for "${flowName}"`}>
          <ForwardedIconComponent name="Brain" className="mr-2 h-4 w-4" />
          Create Memory
        </BaseModal.Header>
        <BaseModal.Content className="flex flex-col gap-6 px-6 py-4">
          {/* Name field */}
          <div className="flex flex-col gap-2">
            <Label htmlFor="memory-name">
              Name <span className="text-destructive">*</span>
            </Label>
            <Input
              id="memory-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Memory name"
            />
          </div>

          {/* Embedding Model picker */}
          <div className="flex flex-col gap-2">
            <Label>
              Embedding Model <span className="text-destructive">*</span>
            </Label>
            <Popover
              open={modelDropdownOpen}
              onOpenChange={setModelDropdownOpen}
            >
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
                        {selectedModel?.name || "Select an embedding model"}
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
                    {Object.entries(groupedModels).map(
                      ([provider, models]) => (
                        <CommandGroup className="p-0" key={provider}>
                          <div className="my-2 ml-4 text-xs font-semibold text-muted-foreground">
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
                                  className="ml-2 h-4 w-4 shrink-0 text-primary"
                                />
                                <div className="truncate text-[13px]">
                                  {model.name}
                                </div>
                                <div className="ml-auto pl-2">
                                  <ForwardedIconComponent
                                    name="Check"
                                    className={cn(
                                      "h-4 w-4 shrink-0 text-primary",
                                      selectedModel?.name === model.name &&
                                        selectedModel?.provider ===
                                          model.provider
                                        ? "opacity-100"
                                        : "opacity-0",
                                    )}
                                  />
                                </div>
                              </div>
                            </CommandItem>
                          ))}
                        </CommandGroup>
                      ),
                    )}
                  </CommandList>
                  <div className="border-t bg-background">
                    <CommandItem
                      value="__manage_providers__"
                      onSelect={() => {
                        setModelDropdownOpen(false);
                        setModelProviderModalOpen(true);
                      }}
                      className="group cursor-pointer rounded-none px-3 py-2 text-xs text-muted-foreground aria-selected:bg-accent"
                    >
                      <div className="flex items-center gap-2 pl-1 group-hover:text-primary group-aria-selected:text-primary">
                        Manage Model Providers
                        <ForwardedIconComponent
                          name="Settings"
                          className="h-4 w-4 text-muted-foreground group-hover:text-primary group-aria-selected:text-primary"
                        />
                      </div>
                    </CommandItem>
                  </div>
                </Command>
              </PopoverContent>
            </Popover>
          </div>

          {/* Batch Size */}
          <div className="flex flex-col gap-2">
            <Label htmlFor="memory-batch-size">Batch Size</Label>
            <span className="text-xs text-muted-foreground">
              Messages to accumulate before ingestion triggers
            </span>
            <Input
              id="memory-batch-size"
              value={batchSizeInput}
              onChange={(e) => {
                // Allow free typing — only digits
                const raw = e.target.value.replace(/[^0-9]/g, "");
                setBatchSizeInput(raw);
              }}
              onBlur={() => {
                // Clamp to valid range on blur
                const val = parseInt(batchSizeInput, 10);
                if (!batchSizeInput || isNaN(val) || val < 1) {
                  setBatchSizeInput("1");
                }
              }}
              placeholder="1"
            />
          </div>

          {/* LLM Preprocessing toggle */}
          <div className="flex items-center justify-between rounded-lg border border-border p-3">
            <div className="flex flex-col gap-0.5">
              <Label className="text-sm">LLM Preprocessing</Label>
              <span className="text-xs text-muted-foreground">
                Summarize messages with an LLM before ingestion
              </span>
            </div>
            <Switch
              checked={preprocessingEnabled}
              onCheckedChange={setPreprocessingEnabled}
            />
          </div>

          {/* LLM Model picker — shown when preprocessing is on */}
          {preprocessingEnabled && (
            <div className="flex flex-col gap-2">
              <Label>
                Preprocessing Model{" "}
                <span className="text-destructive">*</span>
              </Label>
              <Popover
                open={llmModelDropdownOpen}
                onOpenChange={setLlmModelDropdownOpen}
              >
                {!hasLLMProviders && !llmModelsLoading ? (
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
                      disabled={llmModelsLoading}
                      variant="primary"
                      size="xs"
                      role="combobox"
                      ref={llmModelButtonRef}
                      aria-expanded={llmModelDropdownOpen}
                      className={cn(
                        "dropdown-component-false-outline py-2",
                        "w-full justify-between font-normal",
                      )}
                    >
                      <span className="flex w-full items-center gap-2 overflow-hidden">
                        {selectedLLMModel && (
                          <ForwardedIconComponent
                            name={selectedLLMModel.icon || "Bot"}
                            className="h-4 w-4 flex-shrink-0"
                          />
                        )}
                        <span
                          className={cn(
                            "truncate",
                            !selectedLLMModel && "text-muted-foreground",
                          )}
                        >
                          {selectedLLMModel?.name || "Select an LLM model"}
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
                    minWidth:
                      llmModelButtonRef?.current?.clientWidth ?? "200px",
                  }}
                >
                  <Command className="flex flex-col">
                    <CommandList className="max-h-[300px] overflow-y-auto">
                      {Object.entries(groupedLLMModels).map(
                        ([provider, models]) => (
                          <CommandGroup className="p-0" key={provider}>
                            <div className="my-2 ml-4 text-xs font-semibold text-muted-foreground">
                              {provider}
                            </div>
                            {models.map((model) => (
                              <CommandItem
                                key={`${model.provider}::${model.name}`}
                                value={model.name}
                                onSelect={() => handleLLMModelSelect(model)}
                                className="w-full items-center rounded-none"
                              >
                                <div className="flex w-full items-center gap-2">
                                  <ForwardedIconComponent
                                    name={model.icon || "Bot"}
                                    className="ml-2 h-4 w-4 shrink-0 text-primary"
                                  />
                                  <div className="truncate text-[13px]">
                                    {model.name}
                                  </div>
                                  <div className="ml-auto pl-2">
                                    <ForwardedIconComponent
                                      name="Check"
                                      className={cn(
                                        "h-4 w-4 shrink-0 text-primary",
                                        selectedLLMModel?.name ===
                                          model.name &&
                                          selectedLLMModel?.provider ===
                                            model.provider
                                          ? "opacity-100"
                                          : "opacity-0",
                                      )}
                                    />
                                  </div>
                                </div>
                              </CommandItem>
                            ))}
                          </CommandGroup>
                        ),
                      )}
                    </CommandList>
                    <div className="border-t bg-background">
                      <CommandItem
                        value="__manage_llm_providers__"
                        onSelect={() => {
                          setLlmModelDropdownOpen(false);
                          setModelProviderModalOpen(true);
                        }}
                        className="group cursor-pointer rounded-none px-3 py-2 text-xs text-muted-foreground aria-selected:bg-accent"
                      >
                        <div className="flex items-center gap-2 pl-1 group-hover:text-primary group-aria-selected:text-primary">
                          Manage Model Providers
                          <ForwardedIconComponent
                            name="Settings"
                            className="h-4 w-4 text-muted-foreground group-hover:text-primary group-aria-selected:text-primary"
                          />
                        </div>
                      </CommandItem>
                    </div>
                  </Command>
                </PopoverContent>
              </Popover>
            </div>
          )}

          {/* Preprocessing Instructions — shown when preprocessing is on */}
          {preprocessingEnabled && (
            <div className="flex flex-col gap-2">
              <Label htmlFor="memory-preprocessing-prompt">
                Preprocessing Instructions (optional)
              </Label>
              <span className="text-xs text-muted-foreground">
                How the LLM should process each batch of {batchSizeInput || "1"} message{batchSizeInput === "1" ? "" : "s"}.
              </span>
              <Textarea
                id="memory-preprocessing-prompt"
                value={preprocessingPrompt}
                onChange={(e) => setPreprocessingPrompt(e.target.value)}
                placeholder="Produce a concise summary that captures the key facts, decisions, and context."
                className="min-h-[80px] resize-y"
              />
            </div>
          )}
        </BaseModal.Content>
        <BaseModal.Footer
          submit={{
            label: "Create Memory",
            loading: createMemoryMutation.isPending,
            disabled: !name.trim() || !selectedModel,
          }}
        />
      </BaseModal>

      <ModelProviderModal
        open={modelProviderModalOpen}
        setOpen={(open) => {
          setModelProviderModalOpen(open);
          if (!open) {
            refetchModels();
            refetchLLMModels();
          }
        }}
      />
    </>
  );
}
