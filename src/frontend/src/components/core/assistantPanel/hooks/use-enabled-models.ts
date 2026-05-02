import { useMemo } from "react";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";

// Providers whose models run locally inside the langflow process and don't
// (yet) support the agentic assistant code path. They're hidden from the
// assistant's model picker so the auto-default never lands on a local model.
// Once the assistant gains support for local inference, drop the entry.
const LOCAL_INFERENCE_PROVIDERS = new Set(["HuggingFace"]);

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

    return providersData
      .filter(
        (provider) =>
          provider.is_enabled && !LOCAL_INFERENCE_PROVIDERS.has(provider.provider),
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
