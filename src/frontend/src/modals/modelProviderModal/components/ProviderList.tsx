import { useGetModelProviders } from '@/controllers/API/queries/models/use-get-model-providers';
import ProviderListItem from './ProviderListItem';
import { Provider } from './types';

export interface ProviderListProps {
  modeltype: 'llm' | 'embedding';
  onProviderSelect?: (provider: Provider) => void;
  selectedProviderName?: string | null;
}

/**
 * Fetches and displays the list of available model providers.
 * Filters out providers with only deprecated/unsupported models.
 */
const ProviderList = ({
  modeltype,
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

  // Filter out providers that have ANY deprecated + unsupported models
  // A provider with deprecatedCount > 0 is excluded from the list
  const providers: Provider[] = providersData
    .filter(provider => {
      const deprecatedCount = provider?.models?.filter(
        model =>
          model.metadata?.deprecated &&
          model.metadata?.not_supported &&
          model.metadata?.model_type === modeltype
      )?.length;
      return !deprecatedCount;
    })
    .map(provider => ({
      provider: provider.provider,
      icon: provider.icon,
      is_enabled: provider.is_enabled,
      model_count: provider.models?.length || 0,
      models: provider.models || [],
    }));

  if (isLoading || (isFetching && providers.length === 0)) {
    return (
      <div
        className="text-muted-foreground"
        data-testid="provider-list-loading"
      >
        Loading providers...
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1" data-testid="provider-list">
      {providers.map(provider => (
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
