import { useMemo } from "react";
import LoadingTextComponent from "@/components/common/loadingTextComponent";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
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
    return rawProviders
      .map((provider) => {
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
          model_count: matchingModels.length,
          models: matchingModels,
          api_docs_url: provider.api_docs_url,
        };
      })
      .filter((provider) => provider.model_count > 0);
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
