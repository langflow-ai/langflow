import axios from "axios";
import {
  DEFAULT_POLLING_INTERVAL,
  DEFAULT_TIMEOUT,
} from "@/constants/constants";
import { EventDeliveryType } from "@/constants/enums";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
import type { useQueryFunctionType } from "../../../../types/api";
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
  webhook_polling_interval: number;
  serialization_max_items_length: number;
  event_delivery: EventDeliveryType;
  webhook_auth_enable: boolean;
  voice_mode_available: boolean;
  default_folder_name: string;
  hide_getting_started_progress: boolean;
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
  const setSerializationMaxItemsLength = useUtilityStore(
    (state) => state.setSerializationMaxItemsLength,
  );
  const setFeatureFlags = useUtilityStore((state) => state.setFeatureFlags);
  const setWebhookPollingInterval = useUtilityStore(
    (state) => state.setWebhookPollingInterval,
  );
  const setEventDelivery = useUtilityStore((state) => state.setEventDelivery);
  const setWebhookAuthEnable = useUtilityStore(
    (state) => state.setWebhookAuthEnable,
  );
  const setDefaultFolderName = useUtilityStore(
    (state) => state.setDefaultFolderName,
  );
  const setHideGettingStartedProgress = useUtilityStore(
    (state) => state.setHideGettingStartedProgress,
  );

  const { query } = UseRequestProcessor();

  const getConfigFn = async () => {
    const response = await api.get<ConfigResponse>(`${getURL("CONFIG")}`);
    const data = response["data"];
    if (data) {
      const timeoutInMilliseconds = data.frontend_timeout
        ? data.frontend_timeout * 1000
        : DEFAULT_TIMEOUT;
      axios.defaults.baseURL = "";
      axios.defaults.timeout = timeoutInMilliseconds;
      setAutoSaving(data.auto_saving);
      setAutoSavingInterval(data.auto_saving_interval);
      setHealthCheckMaxRetries(data.health_check_max_retries);
      setMaxFileSizeUpload(data.max_file_size_upload);
      setFeatureFlags(data.feature_flags);
      setSerializationMaxItemsLength(data.serialization_max_items_length);
      setWebhookPollingInterval(
        data.webhook_polling_interval ?? DEFAULT_POLLING_INTERVAL,
      );
      setEventDelivery(data.event_delivery ?? EventDeliveryType.POLLING);
      setWebhookAuthEnable(data.webhook_auth_enable ?? true);
      setDefaultFolderName(data.default_folder_name ?? "Starter Project");
      setHideGettingStartedProgress(
        data.hide_getting_started_progress ?? false,
      );
    }
    return data;
  };

  const queryResult = query(["useGetConfig"], getConfigFn, {
    refetchOnWindowFocus: false,
    ...options,
  });

  return queryResult;
};
