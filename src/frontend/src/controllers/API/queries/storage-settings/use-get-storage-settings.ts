import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface StorageSettings {
  default_storage_location: string;
  component_aws_access_key_id: string | null;
  component_aws_secret_access_key: string | null;
  component_aws_default_bucket: string | null;
  component_aws_default_region: string | null;
  component_google_drive_service_account_key: string | null;
  component_google_drive_default_folder_id: string | null;
}

export const useGetStorageSettings: useQueryFunctionType<
  undefined,
  StorageSettings
> = (options?) => {
  const { query } = UseRequestProcessor();

  const getStorageSettingsFn = async (): Promise<StorageSettings> => {
    const res = await api.get(getURL("STORAGE_SETTINGS", {}, true));
    return res.data;
  };

  const queryResult: UseQueryResult<StorageSettings, Error> = query(
    ["useGetStorageSettings"],
    getStorageSettingsFn,
    {
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
