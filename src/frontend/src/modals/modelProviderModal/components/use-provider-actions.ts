import { useQueryClient } from '@tanstack/react-query';
import { useUpdateEnabledModels } from '@/controllers/API/queries/models/use-update-enabled-models';
import { useSetDefaultModel } from '@/controllers/API/queries/models/use-set-default-model';
import { useClearDefaultModel } from '@/controllers/API/queries/models/use-clear-default-model';
import {
  useDeleteGlobalVariables,
  usePostGlobalVariables,
} from '@/controllers/API/queries/variables';
import {
  PROVIDER_VARIABLE_MAPPING,
  VARIABLE_CATEGORY,
} from '@/constants/providerConstants';
import useAlertStore from '@/stores/alertStore';
import { GlobalVariable } from '@/types/global_variables';
import { DefaultModelData } from './types';

export const useProviderActions = () => {
  const queryClient = useQueryClient();
  const { mutate: mutateUpdateEnabledModels } = useUpdateEnabledModels();
  const { mutate: mutateSetDefaultModel } = useSetDefaultModel();
  const { mutate: mutateClearDefaultModel } = useClearDefaultModel();
  const { mutate: mutateDeleteGlobalVariable } = useDeleteGlobalVariables();
  const { mutate: mutateCreateGlobalVariable } = usePostGlobalVariables();
  const setErrorData = useAlertStore(state => state.setErrorData);
  const setSuccessData = useAlertStore(state => state.setSuccessData);

  const handleToggleModel = (
    providerName: string,
    modelName: string,
    enabled: boolean
  ) => {
    mutateUpdateEnabledModels(
      {
        updates: [
          {
            provider: providerName,
            model_id: modelName,
            enabled: enabled,
          },
        ],
      },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ['useGetEnabledModels'] });
          setSuccessData({
            title: `${modelName} ${
              enabled ? 'enabled' : 'disabled'
            } successfully`,
          });
        },
        onError: () => {
          setErrorData({
            title: 'Error updating model',
            list: ['Failed to update model status'],
          });
        },
      }
    );
  };

  const handleBatchToggleModels = (
    updates: Array<{ provider: string; model_id: string; enabled: boolean }>,
    onSuccess?: () => void
  ) => {
    mutateUpdateEnabledModels(
      {
        updates,
      },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ['useGetEnabledModels'] });
          const enabledCount = updates.filter(u => u.enabled).length;
          const disabledCount = updates.filter(u => !u.enabled).length;

          let message = 'Models updated successfully';
          if (enabledCount > 0 && disabledCount > 0) {
            message = `${enabledCount} model${
              enabledCount > 1 ? 's' : ''
            } enabled, ${disabledCount} disabled`;
          } else if (enabledCount > 0) {
            message = `${enabledCount} model${
              enabledCount > 1 ? 's' : ''
            } enabled successfully`;
          } else if (disabledCount > 0) {
            message = `${disabledCount} model${
              disabledCount > 1 ? 's' : ''
            } disabled successfully`;
          }

          setSuccessData({
            title: message,
          });
          onSuccess?.();
        },
        onError: () => {
          setErrorData({
            title: 'Error updating models',
            list: ['Failed to update model status'],
          });
        },
      }
    );
  };

  const handleSetDefaultModel = (
    providerName: string,
    modelName: string,
    modelType: string
  ) => {
    mutateSetDefaultModel(
      {
        model_name: modelName,
        provider: providerName,
        model_type: modelType,
      },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ['useGetDefaultModel'] });
          setSuccessData({
            title: `${modelName} set as default`,
          });
        },
        onError: () => {
          setErrorData({
            title: 'Error setting default model',
            list: ['Failed to set default model'],
          });
        },
      }
    );
  };

  const handleClearDefaultModel = (modelType: string) => {
    mutateClearDefaultModel(
      {
        model_type: modelType,
      },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ['useGetDefaultModel'] });
          setSuccessData({
            title: 'Default model cleared',
          });
        },
        onError: () => {
          setErrorData({
            title: 'Error clearing default model',
            list: ['Failed to clear default model'],
          });
        },
      }
    );
  };

  // Enable a provider that doesn't require an API key (currently only Ollama).
  // For providers requiring API keys, use the API key dialog flow instead.
  const handleEnableProvider = (providerName: string) => {
    const variableName = PROVIDER_VARIABLE_MAPPING[providerName];
    if (!variableName) {
      setErrorData({
        title: 'Error enabling provider',
        list: ['Provider variable mapping not found'],
      });
      return;
    }

    // Default Ollama base URL - this function is currently only used for Ollama
    const defaultBaseUrl = 'http://localhost:11434';

    mutateCreateGlobalVariable(
      {
        name: variableName,
        value: defaultBaseUrl,
        type: VARIABLE_CATEGORY.CREDENTIAL,
        category: VARIABLE_CATEGORY.GLOBAL,
        default_fields: [],
      },
      {
        onSuccess: () => {
          setSuccessData({
            title: `${providerName} enabled successfully`,
          });
          // The mutation already refetches useGetGlobalVariables in onSettled
          // We need to refetch model providers, enabled models, and flows
          queryClient.invalidateQueries({
            queryKey: ['useGetModelProviders'],
          });
          queryClient.invalidateQueries({
            queryKey: ['useGetEnabledModels'],
          });
          queryClient.invalidateQueries({
            queryKey: ['flows'],
          });
        },
        onError: (error: unknown) => {
          const errorMessage =
            error instanceof Error
              ? error.message
              : (error as { response?: { data?: { detail?: string } } })
                  ?.response?.data?.detail ||
                'An unexpected error occurred while enabling the provider. Please try again.';
          setErrorData({
            title: 'Error enabling provider',
            list: [errorMessage],
          });
        },
      }
    );
  };

  const handleDeleteProvider = (
    providerName: string,
    globalVariables: GlobalVariable[] | undefined,
    defaultModelData: DefaultModelData | undefined,
    defaultEmbeddingModelData: DefaultModelData | undefined,
    onSuccess?: () => void
  ) => {
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

    // Check if the provider being deleted has the current default model or embedding
    const shouldClearDefaultModel =
      defaultModelData?.default_model?.provider === providerName;
    const shouldClearDefaultEmbedding =
      defaultEmbeddingModelData?.default_model?.provider === providerName;

    // Clear both default model and embedding if needed
    if (
      shouldClearDefaultModel &&
      shouldClearDefaultEmbedding &&
      defaultModelData?.default_model?.model_type &&
      defaultEmbeddingModelData?.default_model?.model_type
    ) {
      // Clear language model first, then embedding model, then delete provider
      mutateClearDefaultModel(
        {
          model_type: defaultModelData.default_model.model_type,
        },
        {
          onSuccess: () => {
            // After clearing default language model, clear embedding model
            mutateClearDefaultModel(
              {
                model_type: defaultEmbeddingModelData.default_model!.model_type,
              },
              {
                onSuccess: () => {
                  // After clearing both, proceed with provider deletion
                  deleteProviderVariable(variable.id, providerName, onSuccess);
                },
                onError: () => {
                  setErrorData({
                    title: 'Error clearing default embedding',
                    list: [
                      'Failed to clear default embedding before deleting provider',
                    ],
                  });
                },
              }
            );
          },
          onError: () => {
            setErrorData({
              title: 'Error clearing default model',
              list: ['Failed to clear default model before deleting provider'],
            });
          },
        }
      );
    } else if (
      shouldClearDefaultModel &&
      defaultModelData?.default_model?.model_type
    ) {
      // Only clear default language model
      mutateClearDefaultModel(
        {
          model_type: defaultModelData.default_model.model_type,
        },
        {
          onSuccess: () => {
            // After clearing default, proceed with provider deletion
            deleteProviderVariable(variable.id, providerName, onSuccess);
          },
          onError: () => {
            setErrorData({
              title: 'Error clearing default model',
              list: ['Failed to clear default model before deleting provider'],
            });
          },
        }
      );
    } else if (
      shouldClearDefaultEmbedding &&
      defaultEmbeddingModelData?.default_model?.model_type
    ) {
      // Only clear default embedding model
      mutateClearDefaultModel(
        {
          model_type: defaultEmbeddingModelData.default_model.model_type,
        },
        {
          onSuccess: () => {
            // After clearing default, proceed with provider deletion
            deleteProviderVariable(variable.id, providerName, onSuccess);
          },
          onError: () => {
            setErrorData({
              title: 'Error clearing default embedding',
              list: [
                'Failed to clear default embedding before deleting provider',
              ],
            });
          },
        }
      );
    } else {
      // No default model to clear, proceed directly with deletion
      deleteProviderVariable(variable.id, providerName, onSuccess);
    }
  };

  const deleteProviderVariable = (
    variableId: string,
    providerName: string,
    onSuccess?: () => void
  ) => {
    mutateDeleteGlobalVariable(
      { id: variableId },
      {
        onSuccess: () => {
          setSuccessData({
            title: `${providerName} provider removed successfully`,
          });
          // The mutation already refetches useGetModelProviders in onSettled
          // Just invalidate flows, global variables, and default model
          queryClient.invalidateQueries({
            queryKey: ['flows'],
          });
          queryClient.invalidateQueries({
            queryKey: ['useGetDefaultModel'],
          });
          onSuccess?.();
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

  return {
    handleToggleModel,
    handleBatchToggleModels,
    handleSetDefaultModel,
    handleClearDefaultModel,
    handleEnableProvider,
    handleDeleteProvider,
  };
};
