import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
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
      size="x-small"
      onSubmit={handleSubmit}
    >
      <BaseModal.Header
        description={t("memory.createModalDescription", { flowName })}
      >
        <ForwardedIconComponent
          name="BrainCog"
          className="h-6 w-6 pr-1 text-primary"
          aria-hidden="true"
        />
        {t("memory.createModalTitle")}
      </BaseModal.Header>
      <BaseModal.Content className="-mr-6 pr-3 [&::-webkit-scrollbar]:w-1 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-border hover:[&::-webkit-scrollbar-thumb]:bg-muted-foreground">
        <div className="flex h-full w-full flex-col gap-4 pr-3">
          <div className="space-y-2">
            <Label htmlFor="memory-name">
              {t("memory.nameLabel")}{" "}
              <span className="text-destructive">*</span>
            </Label>
            <Input
              id="memory-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("memory.memoryName")}
            />
          </div>

          <div className="space-y-2">
            <Label>
              {t("memory.embeddingModelLabel")}{" "}
              <span className="text-destructive">*</span>
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
                placeholder={t("memory.selectEmbeddingModel")}
                modelType="embeddings"
              />
            </div>
            {selectedEmbeddingModel[0]?.provider && (
              <div className="text-xs text-muted-foreground">
                {t("memory.providerValue", {
                  provider: selectedEmbeddingModel[0].provider,
                })}
              </div>
            )}
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-1.5">
              <Label htmlFor="memory-batch-size">
                {t("memory.batchSize")}{" "}
                <span className="text-destructive">*</span>
              </Label>
              <ShadTooltip content={t("memory.batchSizeTooltip")} side="right">
                <button
                  type="button"
                  tabIndex={0}
                  aria-label={t("memory.batchSizeHelp")}
                  className="cursor-help rounded focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  <ForwardedIconComponent
                    name="Info"
                    className="h-3.5 w-3.5 text-muted-foreground"
                  />
                </button>
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
            <div className="space-y-0.5">
              <Label className="text-sm" htmlFor="llm-preprocessing-switch">
                {t("memory.llmPreprocessingLabel")}
              </Label>
              <div className="text-xs text-muted-foreground">
                {t("memory.llmPreprocessingDescription")}
              </div>
            </div>
            <Switch
              id="llm-preprocessing-switch"
              checked={preprocessingEnabled}
              onCheckedChange={setPreprocessingEnabled}
            />
          </div>

          {preprocessingEnabled && (
            <>
              <div className="space-y-2">
                <Label>
                  {t("memory.preprocessingModelLabel")}{" "}
                  <span className="text-destructive">*</span>
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
                    placeholder={t("memory.selectPreprocessingModel")}
                    modelType="llm"
                  />
                </div>
                {selectedPreprocessingModel[0]?.provider && (
                  <div className="text-xs text-muted-foreground">
                    Provider: {selectedPreprocessingModel[0].provider}
                  </div>
                )}
              </div>
              <div className="space-y-2">
                <div className="flex items-center gap-1.5">
                  <Label htmlFor="preprocessing-prompt">
                    {t("memory.preprocessingInstructionsLabel")}{" "}
                    <span className="text-destructive">*</span>
                  </Label>
                  <ShadTooltip
                    content={
                      <span>
                        {t("memory.preprocessingInstructionsHint")}{" "}
                        <a
                          href="https://docs.langflow.org/memory-bases#preprocessing-prompt-examples"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-0.5 text-tooltip-foreground underline opacity-80 hover:opacity-100"
                        >
                          {t("memory.seePromptExamples")}
                          <ForwardedIconComponent
                            name="ExternalLink"
                            className="h-3 w-3"
                          />
                        </a>
                      </span>
                    }
                    side="right"
                  >
                    <button
                      type="button"
                      tabIndex={0}
                      aria-label="Preprocessing instructions help"
                      className="cursor-help rounded focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    >
                      <ForwardedIconComponent
                        name="Info"
                        className="h-3.5 w-3.5 text-muted-foreground"
                      />
                    </button>
                  </ShadTooltip>
                </div>
                <Textarea
                  id="preprocessing-prompt"
                  value={preprocessingPrompt}
                  onChange={(e) => setPreprocessingPrompt(e.target.value)}
                  className="min-h-[80px] resize-y"
                />
              </div>
            </>
          )}
        </div>
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: t("memory.createModalTitle"),
          icon: <ForwardedIconComponent name="Plus" className="h-4 w-4" />,
          loading: createMemoryMutation.isPending,
          disabled:
            !name.trim() ||
            selectedEmbeddingModel.length === 0 ||
            (preprocessingEnabled && selectedPreprocessingModel.length === 0) ||
            (preprocessingEnabled && !preprocessingPrompt.trim()),
        }}
      />
    </BaseModal>
  );
}
