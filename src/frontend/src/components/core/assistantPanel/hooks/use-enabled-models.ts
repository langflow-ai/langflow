import { useMemo } from "react";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import { isCredentiallessProvider } from "@/utils/providerCategories";

interface FilteredProviderModel {
  model_name: string;
  metadata?: Record<string, unknown>;
}

interface FilteredProvider {
  provider: string;
  icon: string;
  models: FilteredProviderModel[];
}

interface UseEnabledModelsReturn {
  hasEnabledModels: boolean;
  filteredProviders: FilteredProvider[];
  isLoading: boolean;
}

export function useEnabledModels(): UseEnabledModelsReturn {
  const { data: providersData = [], isLoading } = useGetModelProviders({});
  const { data: enabledModelsData } = useGetEnabledModels();

  const filteredProviders = useMemo(() => {
    const enabledModels = enabledModelsData?.enabled_models || {};

    // Hide credentialless (local-inference) providers from the assistant
    // until it learns to route through their adapters — the auto-default
    // shouldn't land on a model the assistant code path can't run.
    return providersData
      .filter(
        (provider) =>
          provider.is_enabled && !isCredentiallessProvider(provider),
      )
      .map((provider) => {
        const providerEnabledModels = enabledModels[provider.provider] || {};
        return {
          provider: provider.provider,
          icon: provider.icon || "Bot",
          models: provider.models
            .filter(
              (model) =>
                providerEnabledModels[model.model_name] === true &&
                !model.model_name.includes("embedding"),
            )
            .map((model) => ({
              model_name: model.model_name,
              metadata: model.metadata as Record<string, unknown> | undefined,
            })),
        };
      })
      .filter((provider) => provider.models.length > 0);
  }, [providersData, enabledModelsData]);

  const hasEnabledModels = filteredProviders.length > 0;

  return { hasEnabledModels, filteredProviders, isLoading };
}
