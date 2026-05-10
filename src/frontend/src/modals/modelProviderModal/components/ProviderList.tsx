import { useMemo } from "react";
import LoadingTextComponent from "@/components/common/loadingTextComponent";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import { isCredentiallessProvider } from "@/utils/providerCategories";
import ProviderListItem from "./ProviderListItem";
import { Provider } from "./types";

// Supported model types for filtering providers
type ModelType = "llm" | "embeddings" | "all";

export interface ProviderListProps {
  modelType: ModelType;
  onProviderSelect?: (provider: Provider) => void;
  selectedProviderName?: string | null;
}

const ProviderList = ({
  modelType,
  onProviderSelect,
  selectedProviderName,
}: ProviderListProps) => {
  const {
    data: rawProviders = [],
    isLoading,
    isFetching,
  } = useGetModelProviders({});

  const filteredProviders: Provider[] = useMemo(() => {
    const items: Provider[] = rawProviders.map((provider) => {
      const matchingModels =
        provider?.models?.filter((model) =>
          modelType === "all"
            ? true
            : model?.metadata?.model_type === modelType,
        ) || [];

      return {
        provider: provider.provider,
        icon: provider.icon,
        is_enabled: provider.is_enabled,
        is_configured: provider.is_configured,
        model_count: matchingModels.length,
        models: matchingModels,
        api_docs_url: provider.api_docs_url,
        // Forward variables so downstream components can derive
        // credentialless/credentialed classification without a hardcoded list.
        variables: provider.variables,
      };
    });

    // Backend sorts by ``is_configured`` then alphabetical, which puts
    // credentialless providers (always configured for free) up with the
    // configured cloud providers even when the user has deactivated them.
    // Re-sort here using the credentialless-aware notion of "active" so
    // deactivated HuggingFace sorts alphabetically with the other
    // not-yet-set-up providers, matching the visual gating in
    // ``ProviderListItem``.
    const isActive = (p: Provider): boolean =>
      isCredentiallessProvider(p)
        ? !!p.is_enabled
        : !!(p.is_enabled || p.is_configured);

    return [...items].sort((a, b) => {
      const activeDiff = Number(isActive(b)) - Number(isActive(a));
      if (activeDiff !== 0) return activeDiff;
      return a.provider.localeCompare(b.provider);
    });
  }, [rawProviders, modelType]);

  const handleProviderSelect = (provider: Provider) => {
    onProviderSelect?.(provider);
  };

  const isLoadingProviders =
    isLoading || (isFetching && filteredProviders.length === 0);

  if (isLoadingProviders) {
    return (
      <div
        className="text-muted-foreground px-4 py-2"
        data-testid="provider-list-loading"
      >
        <LoadingTextComponent text="Loading providers" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1" data-testid="provider-list">
      {filteredProviders.map((provider) => (
        <ProviderListItem
          key={provider.provider}
          provider={provider}
          showIcon={selectedProviderName !== null}
          isSelected={selectedProviderName === provider.provider}
          onSelect={handleProviderSelect}
        />
      ))}
    </div>
  );
};

export default ProviderList;
