import { useState } from "react";
import { StepperModal, StepperModalFooter } from "../stepperModal";
import { FilesPanel } from "./components/FilesPanel";
import { StepConfiguration } from "./components/StepConfiguration";
import { StepReview } from "./components/StepReview";
import { STEP_DESCRIPTIONS, STEP_TITLES } from "./constants";
import { useKnowledgeBaseForm } from "./hooks/useKnowledgeBaseForm";
import type { KnowledgeBaseUploadModalProps } from "./types";

export type {
  KnowledgeBaseFormData,
  KnowledgeBaseUploadModalProps,
} from "./types";

export default function KnowledgeBaseUploadModal({
  open: controlledOpen,
  setOpen: controlledSetOpen,
  onSubmit,
  existingKnowledgeBase,
  hideAdvanced,
}: KnowledgeBaseUploadModalProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  const open = controlledOpen ?? internalOpen;
  const setOpen = controlledSetOpen ?? setInternalOpen;

  const form = useKnowledgeBaseForm({
    open,
    setOpen,
    onSubmit,
    existingKnowledgeBase,
    hideAdvanced,
  });

  const renderStepContent = () => {
    switch (form.currentStep) {
      case 1:
        return (
          <StepConfiguration
            isAddSourcesMode={form.isAddSourcesMode}
            sourceName={form.sourceName}
            onSourceNameChange={form.setSourceName}
            selectedEmbeddingModel={form.selectedEmbeddingModel}
            onEmbeddingModelChange={form.setSelectedEmbeddingModel}
            embeddingModelOptions={form.embeddingModelOptions}
            existingEmbeddingModel={existingKnowledgeBase?.embeddingModel}
            existingEmbeddingIcon={form.selectedEmbeddingModel[0]?.icon}
            chunkSize={form.chunkSize}
            onChunkSizeChange={form.setChunkSize}
            chunkOverlap={form.chunkOverlap}
            onChunkOverlapChange={form.setChunkOverlap}
            separator={form.separator}
            onSeparatorChange={form.setSeparator}
            showAdvanced={form.showAdvanced}
            toggleAdvanced={form.toggleAdvanced}
            onFileSelect={form.handleFileSelect}
            onFolderSelect={form.handleFolderSelect}
            validationErrors={form.validationErrors}
            onFieldChange={form.clearValidationErrors}
            columnConfig={form.columnConfig}
            onColumnConfigChange={form.setColumnConfig}
          />
        );

      case 2:
        return (
          <StepReview
            files={form.files}
            chunkPreviews={form.chunkPreviews}
            isGeneratingPreview={form.isGeneratingPreview}
            currentChunkIndex={form.currentChunkIndex}
            onCurrentChunkIndexChange={form.setCurrentChunkIndex}
            selectedPreviewFileIndex={form.selectedPreviewFileIndex}
            onSelectedPreviewFileIndexChange={form.setSelectedPreviewFileIndex}
            sourceName={form.sourceName}
            totalFileSize={form.totalFileSize}
            chunkSize={form.chunkSize}
            chunkOverlap={form.chunkOverlap}
            separator={form.separator}
            selectedEmbeddingModel={form.selectedEmbeddingModel}
          />
        );
    }
  };

  return (
    <StepperModal
      open={open}
      onOpenChange={(isOpen) => {
        setOpen(isOpen);
        if (!isOpen) form.resetForm();
      }}
      className="bg-background"
      contentClassName="bg-muted"
      currentStep={form.currentStep}
      totalSteps={2}
      title={
        form.isAddSourcesMode ? "Add Sources" : STEP_TITLES[form.currentStep]
      }
      description={STEP_DESCRIPTIONS[form.currentStep]}
      icon="Database"
      height={!hideAdvanced && form.showAdvanced ? "h-[690px]" : "h-[347px]"}
      width="w-[700px]"
      showProgress={false}
      sidePanel={
        <FilesPanel files={form.files} onRemoveFile={form.handleRemoveFile} />
      }
      sidePanelOpen={form.files.length > 0}
      footer={
        <StepperModalFooter
          currentStep={form.currentStep}
          totalSteps={!hideAdvanced && form.showAdvanced ? 2 : 1}
          onBack={form.handleBack}
          onNext={form.handleNext}
          onSubmit={form.handleSubmit}
          nextDisabled={false}
          submitDisabled={false}
          isSubmitting={form.isSubmitting}
          submitLabel={form.isAddSourcesMode ? "Next Step" : "Create"}
          helpLabel={
            !hideAdvanced && form.currentStep === 1
              ? form.showAdvanced
                ? "Hide Sources"
                : "Configure Sources"
              : undefined
          }
          onHelp={
            !hideAdvanced && form.currentStep === 1
              ? form.toggleAdvanced
              : undefined
          }
        />
      }
    >
      {renderStepContent()}
    </StepperModal>
  );
}
