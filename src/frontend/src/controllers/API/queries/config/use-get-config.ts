import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
import axios from "axios";
import { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface ConfigResponse {
  frontend_timeout: number;
  auto_saving: boolean;
  auto_saving_interval: number;
  health_check_max_retries: number;
  max_file_size_upload: number;
  feature_flags: Record<string, any>;
}

export const useGetConfig: useQueryFunctionType<undefined, ConfigResponse> = (
  options,
) => {
  const setAutoSaving = useFlowsManagerStore((state) => state.setAutoSaving);
  const setAutoSavingInterval = useFlowsManagerStore(
    (state) => state.setAutoSavingInterval,
  );
  const setHealthCheckMaxRetries = useFlowsManagerStore(
    (state) => state.setHealthCheckMaxRetries,
  );
  const setMaxFileSizeUpload = useUtilityStore(
    (state) => state.setMaxFileSizeUpload,
  );
  const setFeatureFlags = useUtilityStore((state) => state.setFeatureFlags);

  const { query } = UseRequestProcessor();

  const getConfigFn = async () => {
    const response = await api.get<ConfigResponse>(`${getURL("CONFIG")}`);
    const data = response["data"];
    if (data) {
      const timeoutInMilliseconds = data.frontend_timeout
        ? data.frontend_timeout * 1000
        : 30000;
      axios.defaults.baseURL = "";
      axios.defaults.timeout = timeoutInMilliseconds;
      setAutoSaving(data.auto_saving);
      setAutoSavingInterval(data.auto_saving_interval);
      setHealthCheckMaxRetries(data.health_check_max_retries);
      setMaxFileSizeUpload(data.max_file_size_upload);
      setFeatureFlags(data.feature_flags);
    }
    return data;
  };

  const queryResult = query(["useGetConfig"], getConfigFn, {
    refetchOnWindowFocus: false,
    ...options,
  });

  return queryResult;
};
