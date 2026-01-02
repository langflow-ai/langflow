import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { StorageSettings } from "./use-get-storage-settings";

interface UpdateStorageSettingsParams {
  default_storage_location?: string;
  component_aws_access_key_id?: string;
  component_aws_secret_access_key?: string;
  component_aws_default_bucket?: string;
  component_aws_default_region?: string;
  component_google_drive_service_account_key?: string;
  component_google_drive_default_folder_id?: string;
}

export const useUpdateStorageSettings: useMutationFunctionType<
  undefined,
  UpdateStorageSettingsParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function updateStorageSettings(
    settings: UpdateStorageSettingsParams,
  ): Promise<StorageSettings> {
    const res = await api.patch(getURL("STORAGE_SETTINGS", {}, true), settings);
    return res.data;
  }

  const mutation: UseMutationResult<
    StorageSettings,
    any,
    UpdateStorageSettingsParams
  const mutation: UseMutationResult<
    StorageSettings,
    any,
    UpdateStorageSettingsParams
  > = mutate(["useUpdateStorageSettings"], updateStorageSettings, {
    ...options,
    onSettled: (data, error, variables, context) => {
      queryClient.refetchQueries({ queryKey: ["useGetStorageSettings"] });
      options?.onSettled?.(data, error, variables, context);
    },
    retry: false,
  });

  return mutation;
};
