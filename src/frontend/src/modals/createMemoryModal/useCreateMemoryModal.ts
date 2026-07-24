import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { ModelOption } from "@/components/core/parameterRenderComponent/components/modelInputComponent/types";
import {
  type AvailableDBProviderId,
  type DBProviderConfigValue,
  getDBProviderOption,
  getDefaultDBProviderConfig,
  isDBProviderConfigured,
  toAPIBackendType,
} from "@/constants/dbProviderConstants";
import { useCreateMemory } from "@/controllers/API/queries/memories/use-create-memory";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
import useAlertStore from "@/stores/alertStore";
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
  const { data: modelProviders = [] } = useGetModelProviders({});
  const { data: globalVariables = [], isFetched: areGlobalVariablesFetched } =
    useGetGlobalVariables();

  // Default to the platform's active DB provider (Chroma Cloud / OpenSearch when
  // configured), falling back to local Chroma — identical to Knowledge Bases.
  const defaultBackendSelection = useMemo(
    () => getDefaultDBProviderConfig(globalVariables),
    [globalVariables],
  );

  // Seed the selector from the active provider once global variables load.
  useEffect(() => {
    if (hasAppliedBackendDefaults.current || !areGlobalVariablesFetched) {
      return;
    }
    hasAppliedBackendDefaults.current = true;
    setBackendType(defaultBackendSelection.backendType);
    setBackendConfig(defaultBackendSelection.backendConfig);
  }, [areGlobalVariablesFetched, defaultBackendSelection]);

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

  const backendConfigured = isDBProviderConfigured(
    backendType,
    globalVariables,
  );
  const { setErrorData, setSuccessData } = useAlertStore((state) => ({
    setErrorData: state.setErrorData,
    setSuccessData: state.setSuccessData,
  }));

  const embeddingModelOptions = useMemo(
    () =>
      modelProviders
        .filter((provider) => provider.is_enabled)
        .flatMap((provider) =>
          provider.models
            .filter(
              (model) =>
                model.metadata?.model_type === "embeddings" ||
                model.metadata?.model_type === "embedding",
            )
            .map((model) => ({
              id: model.model_name,
              name: model.model_name,
              icon: provider.icon || "Bot",
              provider: provider.provider,
              metadata: model.metadata,
            })),
        ),
    [modelProviders],
  );

  const llmModelOptions = useMemo(
    () =>
      modelProviders
        .filter((provider) => provider.is_enabled)
        .flatMap((provider) =>
          provider.models
            .filter((model) => model.metadata?.model_type === "llm")
            .map((model) => ({
              id: model.model_name,
              name: model.model_name,
              icon: provider.icon || "Bot",
              provider: provider.provider,
              metadata: model.metadata,
            })),
        ),
    [modelProviders],
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

    if (selectedEmbeddingModel.length === 0) {
      setErrorData({
        title: t("memory.validationError"),
        list: [t("memory.embeddingRequired")],
      });
      return;
    }

    if (preprocessingEnabled && selectedPreprocessingModel.length === 0) {
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
    if (!backendConfigured) {
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
      backend_type: toAPIBackendType(backendType),
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
    backendType,
    handleBackendProviderChange,
    globalVariables,
    backendConfigured,
    createMemoryMutation,
    handleSubmit,
    handleClose,
  };
}
