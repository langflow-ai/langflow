import { useMemo } from "react";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";

interface UseEnabledModelsReturn {
  hasEnabledModels: boolean;
}

export function useEnabledModels(): UseEnabledModelsReturn {
  const { data: providersData = [] } = useGetModelProviders({});
  const { data: enabledModelsData } = useGetEnabledModels();

  const hasEnabledModels = useMemo(() => {
    const enabledModels = enabledModelsData?.enabled_models || {};

    return providersData.some((provider) => {
      if (!provider.is_enabled) return false;
      const providerEnabledModels = enabledModels[provider.provider] || {};
      return provider.models.some(
        (model) =>
          providerEnabledModels[model.model_name] === true &&
          !model.model_name.includes("embedding"),
      );
    });
  }, [providersData, enabledModelsData]);

  return { hasEnabledModels };
}
