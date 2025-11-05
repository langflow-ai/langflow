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
    updates: Array<{ provider: string; model_id: string; enabled: boolean }>
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

  const handleEnableProvider = (providerName: string) => {
    const variableName = PROVIDER_VARIABLE_MAPPING[providerName];
    if (!variableName) {
      setErrorData({
        title: 'Error enabling provider',
        list: ['Provider variable mapping not found'],
      });
      return;
    }

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
          // We need to refetch model providers and flows
          queryClient.invalidateQueries({
            queryKey: ['useGetModelProviders'],
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

    mutateDeleteGlobalVariable(
      { id: variable.id },
      {
        onSuccess: () => {
          setSuccessData({
            title: `${providerName} provider removed successfully`,
          });
          // The mutation already refetches useGetModelProviders in onSettled
          // Just invalidate flows and global variables
          queryClient.invalidateQueries({
            queryKey: ['flows'],
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
