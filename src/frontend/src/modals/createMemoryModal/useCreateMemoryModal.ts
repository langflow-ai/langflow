import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { ModelOption } from "@/components/core/parameterRenderComponent/components/modelInputComponent/types";
import {
  ACTIVE_DB_PROVIDER_VARIABLE,
  type AvailableDBProviderId,
  type DBProviderConfigValue,
  getDBProviderOption,
  getDefaultDBProviderConfig,
  getGlobalVariableValue,
  isDBProviderConfigured,
  toAPIBackendType,
} from "@/constants/dbProviderConstants";
import { isModelEnabledForType } from "@/controllers/API/helpers/enabled-model-policy";
import { useCreateMemory } from "@/controllers/API/queries/memories/use-create-memory";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
import useAlertStore from "@/stores/alertStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { extractApiErrorMessages } from "@/utils/apiError";

interface UseCreateMemoryModalParams {
  flowId: string;
  onSuccess?: (memoryId: string) => void;
  onClose: () => void;
}

export function useCreateMemoryModal({
  flowId,
  onSuccess,
  onClose,
}: UseCreateMemoryModalParams) {
  const [name, setName] = useState("");
  const [selectedEmbeddingModel, setSelectedEmbeddingModel] = useState<
    ModelOption[]
  >([]);
  const [batchSizeInput, setBatchSizeInput] = useState("1");
  const [preprocessingEnabled, setPreprocessingEnabled] = useState(false);
  const [selectedPreprocessingModel, setSelectedPreprocessingModel] = useState<
    ModelOption[]
  >([]);
  const [preprocessingPrompt, setPreprocessingPrompt] = useState("");

  // Vector-store backend for the Memory Base's backing KB. Config is derived
  // entirely from DB Providers settings (global variables) — there is no per-MB
  // config to fill in — so the only gate is whether the chosen provider is
  // configured. Mirrors the Knowledge Base upload modal's provider selection.
  const [backendType, setBackendType] =
    useState<AvailableDBProviderId>("chroma");
  const [backendConfig, setBackendConfig] = useState<
    Record<string, DBProviderConfigValue>
  >({});
  // Cache per-provider config so switching away and back restores the user's
  // (settings-derived) selection instead of resetting it.
  const perProviderConfigsRef = useRef<
    Partial<
      Record<AvailableDBProviderId, Record<string, DBProviderConfigValue>>
    >
  >({});
  const hasAppliedBackendDefaults = useRef(false);

  const { t } = useTranslation();
  const modelProvidersQuery = useGetModelProviders(
    { flowId, purpose: "use" },
    { enabled: Boolean(flowId) },
  );
  const enabledModelsQuery = useGetEnabledModels({
    flowId,
    enabled: Boolean(flowId),
    purpose: "use",
  });
  const globalVariablesQuery = useGetGlobalVariables({
    flowId,
    enabled: Boolean(flowId),
  });
  const globalVariables = globalVariablesQuery.data ?? [];
  const modelCatalogReady = Boolean(
    flowId &&
      modelProvidersQuery.isSuccess &&
      enabledModelsQuery.isSuccess &&
      modelProvidersQuery.fetchStatus === "idle" &&
      enabledModelsQuery.fetchStatus === "idle" &&
      !modelProvidersQuery.isFetching &&
      !enabledModelsQuery.isFetching &&
      !modelProvidersQuery.isError &&
      !enabledModelsQuery.isError,
  );
  const globalVariablesReady = Boolean(
    flowId &&
      globalVariablesQuery.isSuccess &&
      globalVariablesQuery.fetchStatus === "idle" &&
      !globalVariablesQuery.isFetching &&
      !globalVariablesQuery.isError,
  );
  const localVectorStoreAvailable = useUtilityStore(
    (state) => state.localVectorStoreAvailable,
  );

  // Default to the platform's active DB provider (Chroma Cloud / OpenSearch when
  // configured), falling back to local Chroma — identical to Knowledge Bases.
  // When local storage is unavailable (production profile), the fallback is
  // pgVector instead so we never seed a Chroma the create endpoint rejects.
  const defaultBackendSelection = useMemo(
    () =>
      getDefaultDBProviderConfig(globalVariables, localVectorStoreAvailable),
    [globalVariables, localVectorStoreAvailable],
  );

  // Seed the selector from the active provider once global variables load.
  useEffect(() => {
    if (hasAppliedBackendDefaults.current || !globalVariablesReady) {
      return;
    }
    hasAppliedBackendDefaults.current = true;
    setBackendType(defaultBackendSelection.backendType);
    setBackendConfig(defaultBackendSelection.backendConfig);
  }, [defaultBackendSelection, globalVariablesReady]);

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

  const backendConfigured =
    globalVariablesReady &&
    isDBProviderConfigured(
      backendType,
      globalVariables,
      localVectorStoreAvailable,
    );
  const { setErrorData, setSuccessData } = useAlertStore((state) => ({
    setErrorData: state.setErrorData,
    setSuccessData: state.setSuccessData,
  }));

  const embeddingModelOptions = useMemo(() => {
    if (!modelCatalogReady) return [];
    const enabledModelsData = enabledModelsQuery.data;
    if (!enabledModelsData) return [];
    return (modelProvidersQuery.data ?? [])
      .filter((provider) => provider.is_enabled)
      .flatMap((provider) =>
        provider.models
          .filter(
            (model) =>
              (model.metadata?.model_type === "embeddings" ||
                model.metadata?.model_type === "embedding") &&
              isModelEnabledForType(
                enabledModelsData,
                provider.provider,
                model.model_name,
                "embeddings",
              ),
          )
          .map((model) => ({
            id: model.model_name,
            name: model.model_name,
            icon: provider.icon || "Bot",
            provider: provider.provider,
            metadata: model.metadata,
          })),
      );
  }, [enabledModelsQuery.data, modelCatalogReady, modelProvidersQuery.data]);

  const llmModelOptions = useMemo(() => {
    if (!modelCatalogReady) return [];
    const enabledModelsData = enabledModelsQuery.data;
    if (!enabledModelsData) return [];
    return (modelProvidersQuery.data ?? [])
      .filter((provider) => provider.is_enabled)
      .flatMap((provider) =>
        provider.models
          .filter(
            (model) =>
              model.metadata?.model_type === "llm" &&
              isModelEnabledForType(
                enabledModelsData,
                provider.provider,
                model.model_name,
                "llm",
              ),
          )
          .map((model) => ({
            id: model.model_name,
            name: model.model_name,
            icon: provider.icon || "Bot",
            provider: provider.provider,
            metadata: model.metadata,
          })),
      );
  }, [enabledModelsQuery.data, modelCatalogReady, modelProvidersQuery.data]);

  const selectionIsIn = (selection: ModelOption[], options: ModelOption[]) => {
    const selected = selection[0];
    return (
      modelCatalogReady &&
      selected !== undefined &&
      options.some(
        (option) =>
          option.provider === selected.provider &&
          option.name === selected.name,
      )
    );
  };
  const embeddingSelectionAuthorized = selectionIsIn(
    selectedEmbeddingModel,
    embeddingModelOptions,
  );
  const preprocessingSelectionAuthorized = selectionIsIn(
    selectedPreprocessingModel,
    llmModelOptions,
  );

  const resetForm = () => {
    setName("");
    setSelectedEmbeddingModel([]);
    setBatchSizeInput("1");
    setPreprocessingEnabled(false);
    setSelectedPreprocessingModel([]);
    setPreprocessingPrompt("");
    perProviderConfigsRef.current = {};
    // Re-seed from the active provider the next time the modal opens.
    hasAppliedBackendDefaults.current = false;
    setBackendType(defaultBackendSelection.backendType);
    setBackendConfig(defaultBackendSelection.backendConfig);
  };

  const createMemoryMutation = useCreateMemory({
    onSuccess: (data) => {
      setSuccessData({ title: t("memory.createdSuccess") });
      onClose();
      resetForm();
      onSuccess?.(data.id);
    },
    onError: (error: unknown) => {
      setErrorData({
        title: t("memory.createError"),
        list: extractApiErrorMessages(error),
      });
    },
  });

  const handleSubmit = () => {
    if (!flowId) {
      setErrorData({
        title: t("memory.validationError"),
        list: [t("memory.noFlowSelected")],
      });
      return;
    }
    if (!name.trim()) {
      setErrorData({
        title: t("memory.validationError"),
        list: [t("memory.nameRequired")],
      });
      return;
    }

    if (!modelCatalogReady) {
      setErrorData({
        title: t("memory.validationError"),
        list: [t("errors.failedToLoadModels")],
      });
      return;
    }

    if (!embeddingSelectionAuthorized) {
      setErrorData({
        title: t("memory.validationError"),
        list: [t("memory.embeddingRequired")],
      });
      return;
    }

    if (preprocessingEnabled && !preprocessingSelectionAuthorized) {
      setErrorData({
        title: t("memory.validationError"),
        list: [t("memory.preprocessingRequired")],
      });
      return;
    }

    if (preprocessingEnabled && !preprocessingPrompt.trim()) {
      setErrorData({
        title: "Validation error",
        list: ["Please provide preprocessing instructions"],
      });
      return;
    }

    // Block creation only when a *remote* backend isn't configured in DB
    // Providers settings. `isDBProviderConfigured` returns true unconditionally
    // for local Chroma, so the default/local path is never blocked here.
    if (!globalVariablesReady || !backendConfigured) {
      setErrorData({
        title: t("memory.validationError"),
        list: [
          t("memory.dbProviderNotConfigured", {
            provider: getDBProviderOption(backendType).label,
          }),
        ],
      });
      return;
    }

    const parsedThreshold = Math.max(1, parseInt(batchSizeInput, 10) || 1);
    const embeddingSelection = selectedEmbeddingModel[0];
    const hasExplicitActiveProvider = Boolean(
      getGlobalVariableValue(globalVariables, ACTIVE_DB_PROVIDER_VARIABLE),
    );

    createMemoryMutation.mutate({
      name: name.trim(),
      flow_id: flowId,
      embedding_model: embeddingSelection?.name,
      auto_capture: true,
      threshold: parsedThreshold,
      preprocessing: preprocessingEnabled,
      preproc_model: preprocessingEnabled
        ? selectedPreprocessingModel[0]?.name
        : undefined,
      preproc_instructions: preprocessingEnabled
        ? preprocessingPrompt.trim()
        : undefined,
      // `chroma_cloud` collapses to `chroma` for the API; the server
      // discriminates local vs cloud via `backend_config.mode`.
      backend_type:
        !hasExplicitActiveProvider && backendType === "chroma"
          ? undefined
          : toAPIBackendType(backendType),
      backend_config: backendConfig,
    });
  };

  const handleClose = () => {
    onClose();
    resetForm();
  };

  return {
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
    modelCatalogReady,
    globalVariablesReady,
    embeddingSelectionAuthorized,
    preprocessingSelectionAuthorized,
    backendType,
    handleBackendProviderChange,
    globalVariables,
    backendConfigured,
    createMemoryMutation,
    handleSubmit,
    handleClose,
  };
}
