import { useMemo, useState } from "react";
import type { ModelOption } from "@/components/core/parameterRenderComponent/components/modelInputComponent/types";
import { useCreateMemory } from "@/controllers/API/queries/memories/use-create-memory";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
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

  const { data: modelProviders = [] } = useGetModelProviders({});
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
  };

  const createMemoryMutation = useCreateMemory({
    onSuccess: (data) => {
      setSuccessData({ title: "Memory created successfully" });
      onClose();
      resetForm();
      onSuccess?.(data.id);
    },
    onError: (error: unknown) => {
      setErrorData({
        title: "Failed to create memory",
        list: extractApiErrorMessages(error),
      });
    },
  });

  const handleSubmit = () => {
    if (!flowId) {
      setErrorData({
        title: "Validation error",
        list: ["No flow selected"],
      });
      return;
    }
    if (!name.trim()) {
      setErrorData({
        title: "Validation error",
        list: ["Please provide a name for the memory"],
      });
      return;
    }

    if (selectedEmbeddingModel.length === 0) {
      setErrorData({
        title: "Validation error",
        list: ["Please select an embedding model"],
      });
      return;
    }

    if (preprocessingEnabled && selectedPreprocessingModel.length === 0) {
      setErrorData({
        title: "Validation error",
        list: ["Please provide a preprocessing model"],
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
    createMemoryMutation,
    handleSubmit,
    handleClose,
  };
}
