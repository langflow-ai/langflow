import { type AxiosError } from "axios";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { ModelOption } from "@/components/core/parameterRenderComponent/components/modelInputComponent";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import { useCreateKnowledgeBase } from "@/controllers/API/queries/knowledge-bases/use-create-knowledge-base";
import { useGetIngestionJobStatus } from "@/controllers/API/queries/knowledge-bases/use-get-ingestion-job-status";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import useAlertStore from "@/stores/alertStore";
import {
  DEFAULT_CHUNK_OVERLAP,
  DEFAULT_CHUNK_SIZE,
  DEFAULT_SEPARATOR,
  KB_NAME_REGEX,
  MAX_TOTAL_FILE_SIZE,
} from "../constants";
import type {
  ChunkPreview,
  ColumnConfigRow,
  KnowledgeBaseFormData,
  KnowledgeBaseUploadModalProps,
  WizardStep,
} from "../types";
import { formatFileSize } from "../utils";

export function useKnowledgeBaseForm({
  open,
  setOpen,
  onSubmit,
  existingKnowledgeBase,
  hideAdvanced,
  existingKnowledgeBaseNames,
}: Pick<Required<KnowledgeBaseUploadModalProps>, "open" | "setOpen"> &
  Pick<
    KnowledgeBaseUploadModalProps,
    | "onSubmit"
    | "existingKnowledgeBase"
    | "hideAdvanced"
    | "existingKnowledgeBaseNames"
  >) {
  const isAddSourcesMode = !!existingKnowledgeBase;

  // Wizard state
  const [currentStep, setCurrentStep] = useState<WizardStep>(1);

  // Fetch embedding model data from API
  const { data: modelProviders = [] } = useGetModelProviders({});

  // Transform provider data into ModelOption[] for embedding models only
  const embeddingModelOptions = useMemo<ModelOption[]>(() => {
    const options: ModelOption[] = [];
    for (const provider of modelProviders) {
      if (!provider.is_enabled) continue;
      for (const model of provider.models) {
        if (model.metadata?.model_type !== "embeddings") continue;
        options.push({
          id: model.model_name,
          name: model.model_name,
          icon: provider.icon || "Bot",
          provider: provider.provider,
          metadata: model.metadata,
        });
      }
    }
    return options;
  }, [modelProviders]);

  // Form state - Step 1
  const [sourceName, setSourceName] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [chunkSize, setChunkSize] = useState(0);
  const [chunkOverlap, setChunkOverlap] = useState(0);
  const [separator, setSeparator] = useState("");
  const [columnConfig, setColumnConfig] = useState<ColumnConfigRow[]>([
    { column_name: "text", vectorize: true, identifier: true },
  ]);

  // Validation state
  const [validationErrors, setValidationErrors] = useState<
    Record<string, string>
  >({});

  // Form state - Step 2
  const [selectedEmbeddingModel, setSelectedEmbeddingModel] = useState<
    ModelOption[]
  >([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [isFilePanelOpen, setIsFilePanelOpen] = useState(false);

  // Preview state
  const [chunkPreviews, setChunkPreviews] = useState<ChunkPreview[]>([]);
  const [isGeneratingPreview, setIsGeneratingPreview] = useState(false);
  const [currentChunkIndex, setCurrentChunkIndex] = useState(0);
  const [selectedPreviewFileIndex, setSelectedPreviewFileIndex] = useState(0);

  // Async ingestion tracking
  const [ingestionJobId, setIngestionJobId] = useState<string | null>(null);

  // Alert store
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  // Create knowledge base mutation
  const createKnowledgeBase = useCreateKnowledgeBase();

  // Poll for async ingestion job status
  const { data: ingestionJobStatus } = useGetIngestionJobStatus({
    job_id: ingestionJobId,
  });

  // Track ingestion job completion (clear the polling ID on terminal state).
  // Notifications for completion/failure are handled by the polling hook in KnowledgeBasesTab.
  useEffect(() => {
    if (!ingestionJobStatus || !ingestionJobId) return;

    if (
      ingestionJobStatus.status === "completed" ||
      ingestionJobStatus.status === "failed"
    ) {
      setIngestionJobId(null);
    }
  }, [ingestionJobStatus, ingestionJobId]);

  // Initialize form with existing knowledge base data when in Add Sources mode
  useEffect(() => {
    if (existingKnowledgeBase && open) {
      setSourceName(existingKnowledgeBase.name);
      if (existingKnowledgeBase.embeddingModel) {
        const matchingModel = embeddingModelOptions.find(
          (opt) => opt.id === existingKnowledgeBase.embeddingModel,
        );
        if (matchingModel) {
          setSelectedEmbeddingModel([matchingModel]);
        }
      }
      if (existingKnowledgeBase.chunkSize != null) {
        setChunkSize(existingKnowledgeBase.chunkSize);
      } else {
        setChunkSize(DEFAULT_CHUNK_SIZE);
      }
      if (existingKnowledgeBase.chunkOverlap != null) {
        setChunkOverlap(existingKnowledgeBase.chunkOverlap);
      } else {
        setChunkOverlap(DEFAULT_CHUNK_OVERLAP);
      }
      if (existingKnowledgeBase.separator != null) {
        setSeparator(existingKnowledgeBase.separator);
      } else {
        setSeparator(DEFAULT_SEPARATOR);
      }
      // Always enable advanced mode in add-sources mode so the file
      // upload section is visible. Also enable when the KB already has
      // advanced chunking config.
      const hasAdvancedConfig =
        isAddSourcesMode ||
        existingKnowledgeBase.chunkSize != null ||
        existingKnowledgeBase.chunkOverlap != null ||
        existingKnowledgeBase.separator != null;
      if (hasAdvancedConfig) {
        setShowAdvanced(true);
      }
      if (
        existingKnowledgeBase.columnConfig &&
        existingKnowledgeBase.columnConfig.length > 0
      ) {
        setColumnConfig(existingKnowledgeBase.columnConfig);
      }
    }
  }, [existingKnowledgeBase, open, embeddingModelOptions]);

  const resetForm = useCallback(() => {
    setSourceName("");
    setFiles([]);
    setChunkSize(0);
    setChunkOverlap(0);
    setSeparator("");
    setColumnConfig([
      { column_name: "text", vectorize: true, identifier: true },
    ]);
    setSelectedEmbeddingModel([]);
    setChunkPreviews([]);
    setCurrentChunkIndex(0);
    setSelectedPreviewFileIndex(0);
    setCurrentStep(1);
    setIsFilePanelOpen(false);
    setShowAdvanced(false);
    setIngestionJobId(null);
    setValidationErrors({});
  }, []);

  const toggleAdvanced = useCallback(() => {
    setShowAdvanced((prev) => {
      if (prev) {
        // Hiding advanced: reset chunk settings and close panel
        setChunkSize(0);
        setChunkOverlap(0);
        setSeparator("");
        setIsFilePanelOpen(false);
      } else {
        // Showing advanced: apply defaults
        setChunkSize(DEFAULT_CHUNK_SIZE);
        setChunkOverlap(DEFAULT_CHUNK_OVERLAP);
        setSeparator(DEFAULT_SEPARATOR);
      }
      return !prev;
    });
  }, []);

  // Generate chunk previews via backend API
  const generateChunkPreviews = useCallback(async () => {
    if (files.length === 0) {
      setChunkPreviews([]);
      return;
    }

    setIsGeneratingPreview(true);
    try {
      const selectedFile = files[selectedPreviewFileIndex] || files[0];
      const formData = new FormData();
      formData.append("files", selectedFile);
      formData.append("chunk_size", chunkSize.toString());
      formData.append("chunk_overlap", chunkOverlap.toString());
      formData.append("separator", separator);

      const response = await api.post(
        `${getURL("KNOWLEDGE_BASES")}/preview-chunks`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } },
      );

      const filePreview = response.data?.files?.[0];
      const previews: ChunkPreview[] =
        filePreview?.preview_chunks?.map(
          (
            chunk: {
              content: string;
              char_count: number;
              start: number;
              end: number;
            },
            i: number,
          ) => ({
            content: chunk.content,
            index: i,
            metadata: {
              source: selectedFile.name,
              start: chunk.start,
              end: chunk.end,
            },
          }),
        ) ?? [];
      setChunkPreviews(previews);
    } catch (error: unknown) {
      const err = error as AxiosError<{ detail?: string }>;
      setErrorData({
        title: "Failed to generate chunk preview",
        list: [err?.response?.data?.detail || err?.message || "Unknown error"],
      });
      setChunkPreviews([]);
    } finally {
      setIsGeneratingPreview(false);
    }
  }, [files, chunkSize, chunkOverlap, separator, selectedPreviewFileIndex]);

  // Generate previews when entering step 2
  useEffect(() => {
    if (currentStep === 2) {
      generateChunkPreviews();
    }
  }, [currentStep, generateChunkPreviews]);

  const getValidationErrors = useCallback((): Record<string, string> => {
    const errors: Record<string, string> = {};
    const trimmedName = sourceName.trim().replace(/\s+/g, "_");
    if (!trimmedName) {
      errors.sourceName = "Name is required";
    } else if (trimmedName.length < 3 || trimmedName.length > 512) {
      errors.sourceName = "Name must be between 3 and 512 characters";
    } else if (!KB_NAME_REGEX.test(trimmedName)) {
      errors.sourceName =
        "Name must only contain [a-zA-Z0-9._-] and start/end with [a-zA-Z0-9]";
    } else if (
      !isAddSourcesMode &&
      existingKnowledgeBaseNames?.some(
        (name) => name.toLowerCase() === trimmedName.toLowerCase(),
      )
    ) {
      errors.sourceName = "A knowledge base with this name already exists";
    }
    if (!isAddSourcesMode && selectedEmbeddingModel.length === 0) {
      errors.embeddingModel = "Embedding model is required";
    }
    const totalBytes = files.reduce((acc, file) => acc + file.size, 0);
    if (totalBytes > MAX_TOTAL_FILE_SIZE) {
      errors.files = "Total file size exceeds the 1 GB limit";
    }
    return errors;
  }, [
    sourceName,
    isAddSourcesMode,
    selectedEmbeddingModel,
    files,
    existingKnowledgeBaseNames,
  ]);

  const clearValidationErrors = useCallback(() => {
    setValidationErrors({});
  }, []);

  const handleSubmit = async () => {
    const errors = getValidationErrors();
    if (Object.keys(errors).length > 0) {
      setValidationErrors(errors);
      return;
    }

    const selectedModel = selectedEmbeddingModel[0];
    const kbName = sourceName.trim().replace(/\s+/g, "_");
    setIsSubmitting(true);

    try {
      // Create the knowledge base (skip if adding to existing)
      if (!isAddSourcesMode) {
        await createKnowledgeBase.mutateAsync({
          name: kbName,
          embedding_provider: selectedModel.provider || "Unknown",
          embedding_model: selectedModel.id || selectedModel.name,
          column_config: columnConfig,
        });
      }

      // Simple mode: only name + embedding model, no files or chunk params
      if (!showAdvanced && !isAddSourcesMode) {
        const callbackData: KnowledgeBaseFormData = {
          sourceName,
          files: [],
          embeddingModel: selectedEmbeddingModel,
          columnConfig,
        };

        setSuccessData({
          title: `Knowledge base "${sourceName}" created`,
        });

        onSubmit?.(callbackData);
        setOpen(false);
        resetForm();
        return;
      }

      // Fire-and-forget: kick off ingestion without blocking the modal
      if (files.length > 0) {
        const formData = new FormData();
        files.forEach((file) => {
          formData.append("files", file);
        });
        formData.append("source_name", sourceName);
        formData.append("chunk_size", chunkSize.toString());
        formData.append("chunk_overlap", chunkOverlap.toString());
        formData.append("separator", separator);
        formData.append("column_config", JSON.stringify(columnConfig));

        // Don't await — fire and forget. Polling will track status.
        api
          .post(`${getURL("KNOWLEDGE_BASES")}/${kbName}/ingest`, formData, {
            headers: { "Content-Type": "multipart/form-data" },
          })
          .catch((ingestError: unknown) => {
            const err = ingestError as AxiosError<{ detail?: string }>;
            setErrorData({
              title: `Failed to start ingestion for "${sourceName}"`,
              list: [
                err?.response?.data?.detail || err?.message || "Unknown error",
              ],
            });
          });
      }

      const callbackData: KnowledgeBaseFormData = {
        sourceName,
        files,
        embeddingModel: selectedEmbeddingModel,
        chunkSize,
        chunkOverlap,
        separator,
        columnConfig,
      };

      if (isAddSourcesMode) {
        setSuccessData({
          title: `Sources added to "${sourceName}"`,
        });
      } else {
        setSuccessData({
          title: `Knowledge base "${sourceName}" created`,
        });
      }

      onSubmit?.(callbackData);
      setOpen(false);
      resetForm();
    } catch (error: unknown) {
      const err = error as AxiosError<{ detail?: string }>;
      const errorMessage =
        err?.response?.data?.detail ||
        err?.message ||
        "Failed to create knowledge base";
      setErrorData({ title: errorMessage });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = e.target.files;
    if (selectedFiles && selectedFiles.length > 0) {
      setFiles((prev) => [...prev, ...Array.from(selectedFiles)]);
      setIsFilePanelOpen(true);
    }
    e.target.value = "";
  };

  const handleFolderSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = e.target.files;
    if (selectedFiles && selectedFiles.length > 0) {
      setFiles((prev) => [...prev, ...Array.from(selectedFiles)]);
      setIsFilePanelOpen(true);
    }
    e.target.value = "";
  };

  const handleRemoveFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleNext = () => {
    const errors = getValidationErrors();
    if (Object.keys(errors).length > 0) {
      setValidationErrors(errors);
      return;
    }
    setValidationErrors({});
    if (currentStep < 2) {
      setCurrentStep((currentStep + 1) as WizardStep);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep((currentStep - 1) as WizardStep);
    }
  };

  const totalFileSize = useMemo(() => formatFileSize(files), [files]);

  return {
    // Mode
    isAddSourcesMode,

    // Wizard navigation
    currentStep,
    handleNext,
    handleBack,

    // Form fields
    sourceName,
    setSourceName,
    files,
    chunkSize,
    setChunkSize,
    chunkOverlap,
    setChunkOverlap,
    separator,
    setSeparator,
    selectedEmbeddingModel,
    setSelectedEmbeddingModel,
    embeddingModelOptions,

    // Validation
    validationErrors,
    clearValidationErrors,

    // UI state
    showAdvanced,
    toggleAdvanced,
    isFilePanelOpen,
    isSubmitting,

    // Column config
    columnConfig,
    setColumnConfig,

    // Preview
    chunkPreviews,
    isGeneratingPreview,
    currentChunkIndex,
    setCurrentChunkIndex,
    selectedPreviewFileIndex,
    setSelectedPreviewFileIndex,

    // Computed
    totalFileSize,

    // Handlers
    handleSubmit,
    handleFileSelect,
    handleFolderSelect,
    handleRemoveFile,
    resetForm,
  };
}
