import { useState } from 'react';
import { useGetModelProviders } from '@/controllers/API/queries/models/use-get-model-providers';
import { useGetEnabledModels } from '@/controllers/API/queries/models/use-get-enabled-models';
import { useGetDefaultModel } from '@/controllers/API/queries/models/use-get-default-model';
import { useGetGlobalVariables } from '@/controllers/API/queries/variables';
import ApiKeyModal from '@/modals/apiKeyModal';
import ProviderModelsDialog from './provider-models-dialog';
import ProviderListItem from './provider-list-item';
import { useProviderActions } from './use-provider-actions';
import { Provider } from './types';

type ProviderListProps = {
  onProviderSelect?: (provider: Provider) => void;
  selectedProviderName?: string | null;
};

const ProviderList = ({
  onProviderSelect,
  selectedProviderName,
}: ProviderListProps) => {
  const {
    data: providersData = [],
    isLoading,
    isFetching,
  } = useGetModelProviders({});
  const { data: enabledModelsData } = useGetEnabledModels();
  const { data: defaultModelData } = useGetDefaultModel({
    model_type: 'language',
  });
  const { data: defaultEmbeddingModelData } = useGetDefaultModel({
    model_type: 'embedding',
  });
  const { data: globalVariables } = useGetGlobalVariables();

  const {
    handleBatchToggleModels,
    handleSetDefaultModel,
    handleClearDefaultModel,
    handleEnableProvider: handleEnableProviderFromHook,
    handleDeleteProvider,
  } = useProviderActions();

  const [openApiKeyDialog, setOpenApiKeyDialog] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [providerToDelete, setProviderToDelete] = useState<string | null>(null);
  const [openProviderDialog, setOpenProviderDialog] = useState(false);
  const [selectedProviderForDialog, setSelectedProviderForDialog] =
    useState<Provider | null>(null);

  const handleEnableProvider = (providerName: string) => {
    if (providerName === 'Ollama') {
      handleEnableProviderFromHook(providerName);
    } else {
      setOpenApiKeyDialog(true);
      setSelectedProvider(providerName);
    }
  };

  const handleDeleteProviderWithCleanup = (providerName: string) => {
    handleDeleteProvider(
      providerName,
      globalVariables,
      defaultModelData,
      defaultEmbeddingModelData,
      () => {
        setDeleteDialogOpen(false);
        setProviderToDelete(null);
      }
    );
  };

  const handleCardClick = (provider: Provider) => {
    if (provider.model_count && provider.model_count > 0) {
      setSelectedProviderForDialog(provider);
      setOpenProviderDialog(true);
      onProviderSelect?.(provider);
    }
  };

  const filteredProviders: Provider[] = providersData
    .filter(provider => {
      // Exclude providers where all models are deprecated and not supported
      const filteredMetaData = provider?.models?.filter(
        model => model.metadata?.deprecated && model.metadata?.not_supported
      )?.length;

      return !filteredMetaData;
    })
    .map(provider => ({
      provider: provider.provider,
      icon: provider.icon,
      is_enabled: provider.is_enabled,
      model_count: provider.models?.length || 0,
      models: provider.models || [],
    }));

  // Show loading during initial load or when refetching
  if (isLoading || (isFetching && filteredProviders.length === 0)) {
    return <div className="text-muted-foreground">Loading providers...</div>;
  }

  return (
    <>
      <div>
        <div>
          {filteredProviders.map(provider => {
            // Show default model name only if it's from this provider
            const defaultModelForProvider =
              defaultModelData?.default_model?.provider === provider.provider
                ? defaultModelData?.default_model?.model_name
                : null;

            const defaultEmbeddingModelForProvider =
              defaultEmbeddingModelData?.default_model?.provider ===
              provider.provider
                ? defaultEmbeddingModelData?.default_model?.model_name
                : null;

            return (
              <ProviderListItem
                key={provider.provider}
                provider={provider}
                defaultModelName={defaultModelForProvider}
                defaultEmbeddingModelName={defaultEmbeddingModelForProvider}
                isSelected={selectedProviderName === provider.provider}
                onCardClick={handleCardClick}
                onEnableProvider={handleEnableProvider}
                onDeleteProvider={handleDeleteProviderWithCleanup}
                deleteDialogOpen={deleteDialogOpen}
                setDeleteDialogOpen={setDeleteDialogOpen}
                providerToDelete={providerToDelete}
                setProviderToDelete={setProviderToDelete}
              />
            );
          })}
        </div>
      </div>

      {/* <ProviderModelsDialog
        open={openProviderDialog}
        onOpenChange={setOpenProviderDialog}
        provider={selectedProviderForDialog}
        enabledModelsData={enabledModelsData}
        defaultModelData={defaultModelData}
        defaultEmbeddingModelData={defaultEmbeddingModelData}
        onBatchToggleModels={handleBatchToggleModels}
        onSetDefaultModel={handleSetDefaultModel}
        onClearDefaultModel={handleClearDefaultModel}
      /> */}

      <ApiKeyModal
        open={openApiKeyDialog}
        onClose={() => setOpenApiKeyDialog(false)}
        provider={selectedProvider || 'Provider'}
      />
    </>
  );
};

export default ProviderList;
