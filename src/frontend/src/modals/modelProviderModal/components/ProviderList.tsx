import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import ProviderListItem from "./ProviderListItem";
import { Provider } from "./types";

interface ProviderListProps {
  onProviderSelect?: (provider: Provider) => void;
  selectedProviderName?: string | null;
}

const ProviderList = ({
  onProviderSelect,
  selectedProviderName,
}: ProviderListProps) => {
  const {
    data: providersData = [],
    isLoading,
    isFetching,
  } = useGetModelProviders({});

  const handleProviderClick = (provider: Provider) => {
    if (provider.model_count && provider.model_count > 0) {
      onProviderSelect?.(provider);
    }
  };

  const providers: Provider[] = providersData
    .filter((provider) => {
      // Exclude providers where all models are deprecated and not supported
      const deprecatedCount = provider?.models?.filter(
        (model) => model.metadata?.deprecated && model.metadata?.not_supported,
      )?.length;
      return !deprecatedCount;
    })
    .map((provider) => ({
      provider: provider.provider,
      icon: provider.icon,
      is_enabled: provider.is_enabled,
      model_count: provider.models?.length || 0,
      models: provider.models || [],
    }));

  if (isLoading || (isFetching && providers.length === 0)) {
    return <div className="text-muted-foreground">Loading providers...</div>;
  }

  return (
    <div className="flex flex-col gap-1">
      {providers.map((provider) => (
        <ProviderListItem
          key={provider.provider}
          provider={provider}
          isSelected={selectedProviderName === provider.provider}
          onSelect={handleProviderClick}
        />
      ))}
    </div>
  );
};

export default ProviderList;
