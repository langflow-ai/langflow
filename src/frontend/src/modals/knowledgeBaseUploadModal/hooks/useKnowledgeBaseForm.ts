import { type AxiosError } from "axios";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { ModelOption } from "@/components/core/parameterRenderComponent/components/modelInputComponent";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import { useCreateKnowledgeBase } from "@/controllers/API/queries/knowledge-bases/use-create-knowledge-base";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import useAlertStore from "@/stores/alertStore";
import {
  DEFAULT_CHUNK_OVERLAP,
  DEFAULT_CHUNK_SIZE,
  DEFAULT_SEPARATOR,
} from "../constants";
import type {
  ChunkPreview,
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
}: Pick<Required<KnowledgeBaseUploadModalProps>, "open" | "setOpen"> &
  Pick<KnowledgeBaseUploadModalProps, "onSubmit" | "existingKnowledgeBase">) {
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
  const [chunkSize, setChunkSize] = useState<number | undefined>(undefined);
  const [chunkOverlap, setChunkOverlap] = useState<number | undefined>(
    undefined,
  );
  const [separator, setSeparator] = useState<string | undefined>(undefined);

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

  // Alert store
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  // Create knowledge base mutation
  const createKnowledgeBase = useCreateKnowledgeBase();

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
    }
  }, [existingKnowledgeBase, open, embeddingModelOptions]);

  const resetForm = useCallback(() => {
    setSourceName("");
    setFiles([]);
    setChunkSize(undefined);
    setChunkOverlap(undefined);
    setSeparator(undefined);
    setSelectedEmbeddingModel([]);
    setChunkPreviews([]);
    setCurrentChunkIndex(0);
    setSelectedPreviewFileIndex(0);
    setCurrentStep(1);
    setIsFilePanelOpen(false);
    setValidationErrors({});
  }, []);

  const toggleAdvanced = useCallback(() => {
    setShowAdvanced((prev) => {
      if (prev) {
        // Hiding advanced: close panel but keep files
        setIsFilePanelOpen(false);
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
      formData.append(
        "chunk_size",
        (chunkSize ?? DEFAULT_CHUNK_SIZE).toString(),
      );
      formData.append(
        "chunk_overlap",
        (chunkOverlap ?? DEFAULT_CHUNK_OVERLAP).toString(),
      );
      formData.append("separator", separator ?? DEFAULT_SEPARATOR);

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
    } catch (error) {
      console.error("Error generating preview:", error);
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
    if (!sourceName.trim()) {
      errors.sourceName = "Name is required";
    }
    if (!isAddSourcesMode && selectedEmbeddingModel.length === 0) {
      errors.embeddingModel = "Embedding model is required";
    }
    return errors;
  }, [sourceName, isAddSourcesMode, selectedEmbeddingModel]);

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
        });
      }

      // Upload and ingest files
      let ingestResult: { chunks_created?: number } | null = null;
      if (files.length > 0) {
        try {
          const formData = new FormData();
          files.forEach((file) => {
            formData.append("files", file);
          });
          formData.append("source_name", sourceName);
          formData.append(
            "chunk_size",
            (chunkSize ?? DEFAULT_CHUNK_SIZE).toString(),
          );
          formData.append(
            "chunk_overlap",
            (chunkOverlap ?? DEFAULT_CHUNK_OVERLAP).toString(),
          );
          formData.append("separator", separator ?? DEFAULT_SEPARATOR);

          const response = await api.post(
            `${getURL("KNOWLEDGE_BASES")}/${kbName}/ingest`,
            formData,
            {
              headers: { "Content-Type": "multipart/form-data" },
            },
          );
          ingestResult = response.data;
        } catch (ingestError: unknown) {
          const err = ingestError as AxiosError<{ detail?: string }>;
          console.warn("Failed to ingest files:", err);
          if (!isAddSourcesMode) {
            setSuccessData({
              title: `Knowledge base "${sourceName}" created, but file ingestion failed. You can add files later.`,
            });
          } else {
            setErrorData({
              title: "Failed to add sources to knowledge base",
            });
          }
          onSubmit?.({
            sourceName,
            files,
            embeddingModel: selectedEmbeddingModel,
            chunkSize: chunkSize ?? DEFAULT_CHUNK_SIZE,
            chunkOverlap: chunkOverlap ?? DEFAULT_CHUNK_OVERLAP,
            separator: separator ?? DEFAULT_SEPARATOR,
          });
          setOpen(false);
          resetForm();
          return;
        }
      }

      const callbackData: KnowledgeBaseFormData = {
        sourceName,
        files,
        embeddingModel: selectedEmbeddingModel,
        chunkSize: chunkSize ?? DEFAULT_CHUNK_SIZE,
        chunkOverlap: chunkOverlap ?? DEFAULT_CHUNK_OVERLAP,
        separator: separator ?? DEFAULT_SEPARATOR,
      };

      if (isAddSourcesMode) {
        const chunksCreated = ingestResult?.chunks_created || 0;
        setSuccessData({
          title: `Added ${files.length} file(s) with ${chunksCreated} chunks to "${sourceName}"!`,
        });
      } else if (files.length > 0) {
        const chunksCreated = ingestResult?.chunks_created || 0;
        setSuccessData({
          title: `Knowledge base "${sourceName}" created with ${files.length} file(s) and ${chunksCreated} chunks!`,
        });
      } else {
        setSuccessData({
          title: `Knowledge base "${sourceName}" created! You can add files later.`,
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
