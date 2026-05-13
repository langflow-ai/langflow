import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import ModelInputComponent from "@/components/core/parameterRenderComponent/components/modelInputComponent";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/utils/utils";
import BaseModal from "../baseModal";
import { useCreateMemoryModal } from "./useCreateMemoryModal";

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
  const {
    name,
    setName,
    selectedEmbeddingModel,
    setSelectedEmbeddingModel,
    batchSizeInput,
    setBatchSizeInput,
    preprocessingEnabled,
    setPreprocessingEnabled,
    selectedPreprocessingModel,
    setSelectedPreprocessingModel,
    preprocessingPrompt,
    setPreprocessingPrompt,
    embeddingModelOptions,
    llmModelOptions,
    createMemoryMutation,
    handleSubmit,
    handleClose,
  } = useCreateMemoryModal({
    flowId,
    onSuccess,
    onClose: () => setOpen(false),
  });

  if (!open) return <></>;

  return (
    <BaseModal
      open={open}
      setOpen={handleClose}
      size="small-h-full"
      onSubmit={handleSubmit}
    >
      <BaseModal.Header description={`Create a memory for \"${flowName}\"`}>
        <ForwardedIconComponent name="Brain" className="mr-2 h-4 w-4" />
        Create Memory
      </BaseModal.Header>
      <BaseModal.Content className="flex flex-col gap-6 px-6 py-4">
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

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="flex flex-col gap-2 md:col-span-2">
            <Label className="text-sm font-medium">
              Embedding Model <span className="text-destructive">*</span>
            </Label>
            <div className={cn("rounded-md", "[&_button]:h-10")}>
              <ModelInputComponent
                id="memory-embedding-model"
                value={selectedEmbeddingModel}
                editNode={false}
                disabled={false}
                handleOnNewValue={({ value }) => {
                  setSelectedEmbeddingModel(value);
                }}
                options={embeddingModelOptions}
                placeholder="Select embedding model"
                modelType="embeddings"
              />
            </div>
            {selectedEmbeddingModel[0]?.provider && (
              <span className="text-xs text-muted-foreground">
                Provider: {selectedEmbeddingModel[0].provider}
              </span>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-1.5">
            <Label htmlFor="memory-batch-size">Batch Size</Label>
            <ShadTooltip
              content="Number of messages to accumulate before syncing to memory. Use 1 to sync after every message, or a higher value to reduce ingestion frequency and group related context together."
              side="right"
            >
              <span className="cursor-help">
                <ForwardedIconComponent
                  name="Info"
                  className="h-3.5 w-3.5 text-muted-foreground"
                />
              </span>
            </ShadTooltip>
          </div>
          <Input
            id="memory-batch-size"
            value={batchSizeInput}
            onChange={(e) => {
              const raw = e.target.value.replace(/[^0-9]/g, "");
              setBatchSizeInput(raw);
            }}
            onBlur={() => {
              const val = parseInt(batchSizeInput, 10);
              if (!batchSizeInput || Number.isNaN(val) || val < 1) {
                setBatchSizeInput("1");
              }
            }}
            placeholder="1"
          />
        </div>

        <div className="flex items-center justify-between rounded-lg border border-border p-3">
          <div className="flex flex-col gap-0.5">
            <Label className="text-sm" htmlFor="llm-preprocessing-switch">
              LLM Preprocessing
            </Label>
            <span className="text-xs text-muted-foreground">
              Summarize messages with an LLM before ingestion
            </span>
          </div>
          <Switch
            id="llm-preprocessing-switch"
            checked={preprocessingEnabled}
            onCheckedChange={setPreprocessingEnabled}
          />
        </div>

        {preprocessingEnabled && (
          <>
            <div className="flex flex-col gap-2">
              <Label className="text-sm font-medium">
                Preprocessing Model <span className="text-destructive">*</span>
              </Label>
              <div className={cn("rounded-md", "[&_button]:h-10")}>
                <ModelInputComponent
                  id="memory-preprocessing-model"
                  value={selectedPreprocessingModel}
                  editNode={false}
                  disabled={false}
                  handleOnNewValue={({ value }) => {
                    setSelectedPreprocessingModel(value);
                  }}
                  options={llmModelOptions}
                  placeholder="Select preprocessing model"
                  modelType="llm"
                />
              </div>
              {selectedPreprocessingModel[0]?.provider && (
                <span className="text-xs text-muted-foreground">
                  Provider: {selectedPreprocessingModel[0].provider}
                </span>
              )}
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="preprocessing-prompt">
                Preprocessing Instructions (optional)
              </Label>
              <Textarea
                id="preprocessing-prompt"
                value={preprocessingPrompt}
                onChange={(e) => setPreprocessingPrompt(e.target.value)}
                placeholder="Produce a concise summary that captures key facts and context."
                className="min-h-[80px] resize-y"
              />
            </div>
          </>
        )}
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: "Create Memory",
          icon: <ForwardedIconComponent name="Plus" className="h-4 w-4" />,
          loading: createMemoryMutation.isPending,
          disabled:
            !name.trim() ||
            selectedEmbeddingModel.length === 0 ||
            (preprocessingEnabled && selectedPreprocessingModel.length === 0),
        }}
      />
    </BaseModal>
  );
}
