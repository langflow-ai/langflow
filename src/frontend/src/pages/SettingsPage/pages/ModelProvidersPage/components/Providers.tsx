import { useState } from 'react';
import { ForwardedIconComponent } from '@/components/common/genericIconComponent';
import { Button } from '@/components/ui/button';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { PROVIDER_VARIABLE_MAPPING } from '@/constants/providerConstants';
import { useGetModelProviders } from '@/controllers/API/queries/models/use-get-model-providers';
import {
  useDeleteGlobalVariables,
  useGetGlobalVariables,
} from '@/controllers/API/queries/variables';
import ApiKeyModal from '@/modals/apiKeyModal';
import DeleteConfirmationModal from '@/modals/deleteConfirmationModal';
import useAlertStore from '@/stores/alertStore';
import { cn } from '@/utils/utils';
import { Checkbox } from '@/components/ui/checkbox';

type Provider = {
  provider: string;
  icon?: string;
  is_enabled: boolean;
  model_count?: number;
  models?: { model_name: string; metadata: Record<string, any> }[];
};

const Providers = ({ type }: { type: 'enabled' | 'available' }) => {
  const { data: providersData = [], isLoading } = useGetModelProviders();
  const { data: globalVariables } = useGetGlobalVariables();
  const { mutate: mutateDeleteGlobalVariable } = useDeleteGlobalVariables();
  const setErrorData = useAlertStore(state => state.setErrorData);
  const setSuccessData = useAlertStore(state => state.setSuccessData);

  const [openApiKeyDialog, setOpenApiKeyDialog] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [providerToDelete, setProviderToDelete] = useState<string | null>(null);

  const handleDeleteProvider = (providerName: string) => {
    if (!globalVariables) return;

    const variableName = PROVIDER_VARIABLE_MAPPING[providerName];
    if (!variableName) {
      setErrorData({
        title: 'Error deleting provider',
        list: ['Provider variable mapping not found'],
      });
      return;
    }

    const variable = globalVariables.find(v => v.name === variableName);
    if (!variable?.id) {
      setErrorData({
        title: 'Error deleting provider',
        list: ['API key not found for this provider'],
      });
      return;
    }

    mutateDeleteGlobalVariable(
      { id: variable.id },
      {
        onSuccess: () => {
          setSuccessData({
            title: `${providerName} provider removed successfully`,
          });
          setDeleteDialogOpen(false);
          setProviderToDelete(null);
        },
        onError: () => {
          setErrorData({
            title: 'Error deleting provider',
            list: ['Failed to remove API key'],
          });
        },
      }
    );
  };

  // Filter providers based on enabled status
  const filteredProviders: Provider[] = providersData
    .filter(provider => {
      return type === 'enabled' ? provider.is_enabled : !provider.is_enabled;
    })
    .map(provider => ({
      provider: provider.provider,
      icon: provider.icon,
      is_enabled: provider.is_enabled,
      model_count: provider.models?.length || 0,
      models: provider.models || [],
    }));

  if (isLoading) {
    return <div className="text-muted-foreground">Loading providers...</div>;
  }

  return (
    <>
      <div>
        <h2 className="text-muted-foreground text-sm--medium">
          {type.charAt(0).toUpperCase() + type.slice(1)}
        </h2>
        <Accordion type="multiple">
          {filteredProviders.map(provider => (
            <AccordionItem
              key={provider.provider}
              value={provider.provider}
              className="border-b-0"
            >
              <div
                className={cn(
                  'flex items-center my-2 py-1 relative hover:bg-transparent'
                )}
              >
                <ForwardedIconComponent
                  name={provider.icon || 'Bot'}
                  className="w-4 h-4 mx-3"
                />

                <AccordionTrigger
                  className={cn(
                    'flex-1 py-0 hover:no-underline hover:bg-transparent',
                    provider.model_count && provider.model_count > 0
                      ? ''
                      : 'pointer-events-none'
                  )}
                  disabled={!provider.model_count || provider.model_count === 0}
                >
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold pl-1 truncate">
                      {provider.provider}
                    </h3>
                    {provider.model_count && (
                      <p
                        className={cn(
                          'text-muted-foreground pr-2',
                          type === 'enabled' && 'text-accent-emerald-foreground'
                        )}
                      >
                        {provider.model_count}{' '}
                        {provider.model_count === 1 ? 'model' : 'models'}
                      </p>
                    )}
                  </div>
                </AccordionTrigger>

                <div className="flex items-center ml-auto">
                  {type === 'enabled' ? (
                    <DeleteConfirmationModal
                      open={
                        deleteDialogOpen &&
                        providerToDelete === provider.provider
                      }
                      setOpen={open => {
                        setDeleteDialogOpen(open);
                        if (!open) setProviderToDelete(null);
                      }}
                      onConfirm={e => {
                        e.stopPropagation();
                        if (providerToDelete) {
                          handleDeleteProvider(providerToDelete);
                        }
                      }}
                      description={`access to ${provider.provider}`}
                      note="You can re-enable this provider at any time by adding your API key again"
                    >
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={e => {
                          e.stopPropagation();
                          setProviderToDelete(provider.provider);
                          setDeleteDialogOpen(true);
                        }}
                        className="p-2"
                      >
                        <ForwardedIconComponent
                          name="Trash"
                          className="text-destructive"
                        />
                      </Button>
                    </DeleteConfirmationModal>
                  ) : (
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={e => {
                        e.stopPropagation();
                        setOpenApiKeyDialog(true);
                        setSelectedProvider(provider.provider);
                      }}
                      className="p-2"
                    >
                      <ForwardedIconComponent
                        name="Plus"
                        className="hover:text-primary text-muted-foreground"
                      />
                    </Button>
                  )}
                </div>
              </div>

              <AccordionContent>
                {provider.models && provider.models.length > 0 ? (
                  <div className="space-y-1">
                    {provider.models.map((model, index) => (
                      <div
                        key={`${model.model_name}-${index}`}
                        className="flex items-center ml-3"
                      >
                        {false ? (
                          <Checkbox
                            checked={true}
                            onCheckedChange={() => {}}
                            disabled={type === 'available'}
                          />
                        ) : (
                          <div className="mr-4" />
                        )}
                        <div className={cn('text-sm py-1 pr-2 pl-5')}>
                          {model.model_name}
                        </div>
                        {model.metadata.reasoning && (
                          <div className="flex items-center space-x-1 text-muted-foreground">
                            <ForwardedIconComponent
                              name="Brain"
                              className="w-4 h-4"
                            />
                            <span className="italic pl-1">Reasoning</span>
                          </div>
                        )}
                        {model.metadata.model_type === 'embeddings' && (
                          <div className="flex items-center space-x-1 text-muted-foreground">
                            <ForwardedIconComponent
                              name="layers"
                              className="w-4 h-4"
                            />
                            <span className="italic pl-1">Embeddings</span>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="ml-12 text-sm text-muted-foreground py-1 px-2">
                    No models available
                  </div>
                )}
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>
      <ApiKeyModal
        open={openApiKeyDialog}
        onClose={() => setOpenApiKeyDialog(false)}
        provider={selectedProvider || 'Provider'}
      />
    </>
  );
};

export default Providers;
