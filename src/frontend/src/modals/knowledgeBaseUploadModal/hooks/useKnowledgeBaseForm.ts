import { type AxiosError } from "axios";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { ModelOption } from "@/components/core/parameterRenderComponent/components/modelInputComponent";
import {
  type AvailableDBProviderId,
  type DBProviderConfigValue,
  getDBProviderOption,
  getDefaultDBProviderConfig,
  isDBProviderConfigured,
  resolveUIBackendType,
  toAPIBackendType,
} from "@/constants/dbProviderConstants";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import { useCreateKnowledgeBase } from "@/controllers/API/queries/knowledge-bases/use-create-knowledge-base";
import { useGetIngestionJobStatus } from "@/controllers/API/queries/knowledge-bases/use-get-ingestion-job-status";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
import useAlertStore from "@/stores/alertStore";
import {
  type MetadataPair,
  metadataPairsToFormValue,
} from "../components/MetadataEditor";
import { validateMetadataPairs } from "../components/metadataValidation";
import {
  DEFAULT_CHUNK_OVERLAP,
  DEFAULT_CHUNK_SIZE,
  DEFAULT_SEPARATOR,
  KB_INGEST_EXTENSIONS,
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

/**
 * Per-backend required-field check. Returns ``null`` when the config
 * is acceptable, or a human-readable message otherwise. Mirrors the
 * server-side validation in each backend's ``_build_vector_store`` so
 * the user sees the problem inline before the request ever lands.
 *
 * Only the actively-registered providers (Chroma + OpenSearch) are
 * validated here — see ``DBProviderInput`` for the UI side. Stubbed
 * providers (mongodb / astra / postgres) are rejected up front by the
 * server schema validator.
 */
function validateBackendConfig(
  backendType: AvailableDBProviderId,
  config: Record<string, DBProviderConfigValue>,
): string | null {
  if (backendType === "chroma_cloud") {
    // API key is validated by isDBProviderConfigured; no literal fields here.
    return null;
  }
  if (backendType === "opensearch") {
    const indexName = config.index_name;
    if (typeof indexName !== "string" || !indexName.trim()) {
      return "OpenSearch requires an index_name";
    }
  }
  return null;
}

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
  const { t } = useTranslation();
  const isAddSourcesMode = !!existingKnowledgeBase;

  // Wizard state
  const [currentStep, setCurrentStep] = useState<WizardStep>(1);

  // Fetch embedding model data from API. Include deprecated entries so the
  // picker can surface them with a "Deprecated" badge instead of dropping them.
  const { data: modelProviders = [] } = useGetModelProviders({
    includeDeprecated: true,
  });
  const { data: globalVariables = [], isFetched: areGlobalVariablesFetched } =
    useGetGlobalVariables();
  const hasAppliedBackendDefaults = useRef(false);

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
  const [chunkSize, setChunkSize] = useState(DEFAULT_CHUNK_SIZE);
  const [chunkOverlap, setChunkOverlap] = useState(DEFAULT_CHUNK_OVERLAP);
  const [separator, setSeparator] = useState(DEFAULT_SEPARATOR);
  const [metadataPairs, setMetadataPairs] = useState<MetadataPair[]>([]);
  const [perFileMetadata, setPerFileMetadata] = useState<
    Record<string, MetadataPair[]>
  >({});
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
  // Defaults keep existing KBs on the local Chroma store. Backend is immutable
  // after create, so add-sources mode displays the existing backend read-only.
  const [backendType, setBackendType] =
    useState<AvailableDBProviderId>("chroma");
  const [backendConfig, setBackendConfig] = useState<
    Record<string, DBProviderConfigValue>
  >({});
  // Persists per-provider configs across provider switches within the modal
  // so that switching away and back restores the config seen on first entry.
  const perProviderConfigsRef = useRef<
    Partial<
      Record<AvailableDBProviderId, Record<string, DBProviderConfigValue>>
    >
  >({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(!hideAdvanced);

  const defaultBackendSelection = useMemo(
    () => getDefaultDBProviderConfig(globalVariables),
    [globalVariables],
  );
  const [isFilePanelOpen, setIsFilePanelOpen] = useState(false);

  // Combined provider-switch handler. Saves the current config under the
  // outgoing provider key and restores any previously cached config for the
  // incoming provider, falling back to the freshly-hydrated config from the
  // dropdown when no prior selection exists.
  const handleBackendProviderChange = useCallback(
    (
      newType: AvailableDBProviderId,
      freshConfig: Record<string, DBProviderConfigValue>,
    ) => {
      perProviderConfigsRef.current[backendType] = backendConfig;
      const restored = perProviderConfigsRef.current[newType] ?? freshConfig;
      setBackendType(newType);
      setBackendConfig(restored);
    },
    [backendType, backendConfig],
  );

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
      if (hasAdvancedConfig && !hideAdvanced) {
        setShowAdvanced(true);
      }
      if (
        existingKnowledgeBase.columnConfig &&
        existingKnowledgeBase.columnConfig.length > 0
      ) {
        setColumnConfig(existingKnowledgeBase.columnConfig);
      }
      setBackendType(
        resolveUIBackendType(
          existingKnowledgeBase.backendType,
          existingKnowledgeBase.backendConfig as
            | Record<string, unknown>
            | undefined,
        ),
      );
      setBackendConfig(
        (existingKnowledgeBase.backendConfig as Record<
          string,
          DBProviderConfigValue
        >) || {},
      );
    }
  }, [existingKnowledgeBase, open, embeddingModelOptions]);

  useEffect(() => {
    if (!open) {
      hasAppliedBackendDefaults.current = false;
      return;
    }
    if (
      existingKnowledgeBase ||
      hasAppliedBackendDefaults.current ||
      !areGlobalVariablesFetched
    ) {
      return;
    }

    setBackendType(defaultBackendSelection.backendType);
    setBackendConfig(defaultBackendSelection.backendConfig);
    hasAppliedBackendDefaults.current = true;
  }, [
    areGlobalVariablesFetched,
    defaultBackendSelection,
    existingKnowledgeBase,
    open,
  ]);

  const resetForm = useCallback(() => {
    setSourceName("");
    setFiles([]);
    setChunkSize(DEFAULT_CHUNK_SIZE);
    setChunkOverlap(DEFAULT_CHUNK_OVERLAP);
    setSeparator(DEFAULT_SEPARATOR);
    setColumnConfig([
      { column_name: "text", vectorize: true, identifier: true },
    ]);
    setSelectedEmbeddingModel([]);
    setBackendType("chroma");
    setBackendConfig({});
    perProviderConfigsRef.current = {};
    setMetadataPairs([]);
    setPerFileMetadata({});
    setChunkPreviews([]);
    setCurrentChunkIndex(0);
    setSelectedPreviewFileIndex(0);
    setCurrentStep(1);
    setIsFilePanelOpen(false);
    setShowAdvanced(!hideAdvanced);
    setIngestionJobId(null);
    setValidationErrors({});
    hasAppliedBackendDefaults.current = false;
  }, [hideAdvanced]);

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
        title: t("knowledge.errorChunkPreview"),
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
      errors.sourceName = t("knowledge.validationNameRequired");
    } else if (trimmedName.length < 3 || trimmedName.length > 512) {
      errors.sourceName = t("knowledge.validationNameLength");
    } else if (!KB_NAME_REGEX.test(trimmedName)) {
      errors.sourceName = t("knowledge.validationNameFormat");
    } else if (
      !isAddSourcesMode &&
      existingKnowledgeBaseNames?.some(
        (name) => name.toLowerCase() === trimmedName.toLowerCase(),
      )
    ) {
      errors.sourceName = t("knowledge.validationNameDuplicate");
    }
    if (!isAddSourcesMode && selectedEmbeddingModel.length === 0) {
      errors.embeddingModel = t("knowledge.validationEmbeddingRequired");
    }
    if (!isAddSourcesMode) {
      const selectedProvider = getDBProviderOption(backendType);
      if (!isDBProviderConfigured(backendType, globalVariables)) {
        errors.backend = `${selectedProvider.label} must be configured in DB Providers settings before it can be used.`;
      } else {
        const backendErrors = validateBackendConfig(backendType, backendConfig);
        if (backendErrors) {
          errors.backend = backendErrors;
        }
      }
    }
    const totalBytes = files.reduce((acc, file) => acc + file.size, 0);
    if (totalBytes > MAX_TOTAL_FILE_SIZE) {
      errors.files = t("knowledge.validationFileSizeLimit");
    }
    const runMetadataValidation = validateMetadataPairs(metadataPairs);
    if (!runMetadataValidation.ok) {
      errors.metadata =
        "Fix metadata fields before continuing. Keys must be 1-32 lowercase letters, digits, or underscores and must be unique.";
    }
    for (const [fileName, pairs] of Object.entries(perFileMetadata)) {
      const perFileValidation = validateMetadataPairs(pairs);
      if (!perFileValidation.ok) {
        errors.metadata = `Fix metadata fields for "${fileName}" before continuing.`;
        break;
      }
    }
    return errors;
  }, [
    t,
    sourceName,
    isAddSourcesMode,
    selectedEmbeddingModel,
    backendType,
    backendConfig,
    globalVariables,
    files,
    existingKnowledgeBaseNames,
    metadataPairs,
    perFileMetadata,
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
          model_selection: selectedModel,
          column_config: columnConfig,
          backend_type: toAPIBackendType(backendType),
          backend_config: backendConfig,
        });
      }

      // Simple mode: only name + embedding model, no files or chunk params.
      if (!showAdvanced && !isAddSourcesMode) {
        const callbackData: KnowledgeBaseFormData = {
          sourceName,
          files: [],
          embeddingModel: selectedEmbeddingModel,
          columnConfig,
          backendType,
          backendConfig,
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

        // User-supplied metadata is sent as JSON strings so the same
        // multipart payload carries run-level + per-file overrides.
        // Empty strings are sent through as-is and the API treats them as
        // ``no metadata supplied``.
        const runMetadata = metadataPairsToFormValue(metadataPairs);
        if (runMetadata) {
          formData.append("metadata", runMetadata);
        }
        const perFileMetadataPayload: Record<
          string,
          Record<string, string>
        > = {};
        for (const [fileName, pairs] of Object.entries(perFileMetadata)) {
          const encoded = metadataPairsToFormValue(pairs);
          if (encoded) {
            perFileMetadataPayload[fileName] = JSON.parse(encoded);
          }
        }
        if (Object.keys(perFileMetadataPayload).length > 0) {
          formData.append(
            "per_file_metadata",
            JSON.stringify(perFileMetadataPayload),
          );
        }

        // Don't await — fire and forget. Polling will track status.
        api
          .post(`${getURL("KNOWLEDGE_BASES")}/${kbName}/ingest`, formData, {
            headers: { "Content-Type": "multipart/form-data" },
          })
          .catch((ingestError: unknown) => {
            const err = ingestError as AxiosError<{ detail?: string }>;
            setErrorData({
              title: t("knowledge.errorIngestion", { name: sourceName }),
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
        backendType,
        backendConfig,
      };

      if (isAddSourcesMode) {
        setSuccessData({
          title: t("knowledge.successSourcesAdded", { name: sourceName }),
        });
      } else {
        setSuccessData({
          title: t("knowledge.baseCreated", { name: sourceName }),
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
        t("knowledge.errorCreateFailed");
      setErrorData({ title: errorMessage });
    } finally {
      setIsSubmitting(false);
    }
  };

  const processSelectedFiles = (selectedFiles: FileList | null) => {
    if (selectedFiles && selectedFiles.length > 0) {
      const allFiles = Array.from(selectedFiles);
      const filteredFiles: File[] = [];
      const excludedFiles: string[] = [];

      for (const file of allFiles) {
        const extension = file.name.split(".").pop()?.toLowerCase();
        if (extension && KB_INGEST_EXTENSIONS.includes(extension)) {
          filteredFiles.push(file);
        } else {
          excludedFiles.push(file.name);
        }
      }

      if (filteredFiles.length > 0) {
        setFiles((prev) => [...prev, ...filteredFiles]);
        setIsFilePanelOpen(true);
      }

      if (excludedFiles.length > 0) {
        setErrorData({
          title:
            "Some files were skipped. Only supported file types were uploaded. Excluded files:",
          list: excludedFiles,
        });
      }
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    processSelectedFiles(e.target.files);
    e.target.value = "";
  };

  const handleFolderSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    processSelectedFiles(e.target.files);
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
    backendType,
    setBackendType,
    backendConfig,
    setBackendConfig,
    handleBackendProviderChange,
    globalVariables,

    // Validation
    validationErrors,
    clearValidationErrors,

    // UI state
    showAdvanced,
    isFilePanelOpen,
    isSubmitting,

    // Column config
    columnConfig,
    setColumnConfig,

    // User metadata
    metadataPairs,
    setMetadataPairs,
    perFileMetadata,
    setPerFileMetadata,

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
