import { useCallback, useMemo } from "react";
import { isModelEnabledForType } from "@/controllers/API/helpers/enabled-model-policy";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { AssistantModel } from "../assistant-panel.types";

interface FilteredProvider {
  provider: string;
  icon: string;
  models: Array<{ model_name: string }>;
}

interface UseEnabledModelsReturn {
  hasEnabledModels: boolean;
  filteredProviders: FilteredProvider[];
  isLoading: boolean;
  isError: boolean;
  isCatalogReady: boolean;
  isModelEnabled: (model: AssistantModel | null) => boolean;
}

export function useEnabledModels(): UseEnabledModelsReturn {
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const providersQuery = useGetModelProviders(
    { flowId: currentFlowId, purpose: "use" },
    { enabled: Boolean(currentFlowId) },
  );
  const enabledModelsQuery = useGetEnabledModels({
    flowId: currentFlowId,
    enabled: Boolean(currentFlowId),
    purpose: "use",
  });
  const isError = providersQuery.isError || enabledModelsQuery.isError;
  const isCatalogReady = Boolean(
    currentFlowId &&
      providersQuery.isSuccess &&
      enabledModelsQuery.isSuccess &&
      providersQuery.fetchStatus === "idle" &&
      enabledModelsQuery.fetchStatus === "idle" &&
      !providersQuery.isFetching &&
      !enabledModelsQuery.isFetching &&
      !isError,
  );

  const filteredProviders = useMemo(() => {
    if (!isCatalogReady) return [];

    const enabledModelsData = enabledModelsQuery.data;
    if (!enabledModelsData) return [];

    return (providersQuery.data ?? [])
      .filter((provider) => provider.is_enabled)
      .map((provider) => {
        return {
          provider: provider.provider,
          icon: provider.icon || "Bot",
          models: provider.models.filter(
            (model) =>
              model.metadata?.model_type === "llm" &&
              isModelEnabledForType(
                enabledModelsData,
                provider.provider,
                model.model_name,
                "llm",
              ),
          ),
        };
      })
      .filter((provider) => provider.models.length > 0);
  }, [enabledModelsQuery.data, isCatalogReady, providersQuery.data]);

  const hasEnabledModels = filteredProviders.length > 0;
  const enabledModelIds = useMemo(
    () =>
      new Set(
        filteredProviders.flatMap((provider) =>
          provider.models.map(
            (model) => `${provider.provider}::${model.model_name}`,
          ),
        ),
      ),
    [filteredProviders],
  );
  const isModelEnabled = useCallback(
    (model: AssistantModel | null) =>
      isCatalogReady &&
      model !== null &&
      enabledModelIds.has(`${model.provider}::${model.name}`),
    [enabledModelIds, isCatalogReady],
  );
  const isLoading = !isCatalogReady && !isError;

  return {
    hasEnabledModels,
    filteredProviders,
    isLoading,
    isError,
    isCatalogReady,
    isModelEnabled,
  };
}
