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

// Base config - common fields shared by all responses
interface BaseConfig {
  type: "public" | "full";
  frontend_timeout: number;
  max_file_size_upload: number;
  event_delivery: EventDeliveryType;
  voice_mode_available: boolean;
}

// Public config = base config (unauthenticated users get only base fields)
export type PublicConfigResponse = BaseConfig;

// Full config = base + authenticated-only fields
export interface ConfigResponse extends BaseConfig {
  auto_saving: boolean;
  auto_saving_interval: number;
  health_check_max_retries: number;
  feature_flags: Record<string, any>;
  webhook_polling_interval: number;
  serialization_max_items_length: number;
  webhook_auth_enable: boolean;
  default_folder_name: string;
  hide_getting_started_progress: boolean;
}

// Union type for the response (can be either public or full config)
export type ConfigResponseType = PublicConfigResponse | ConfigResponse;

// Type guard to check if response is full config (uses type discriminator)
export const isFullConfig = (
  config: ConfigResponseType,
): config is ConfigResponse => {
  return config.type === "full";
};

export const useGetConfig: useQueryFunctionType<
  undefined,
  ConfigResponseType
> = (options) => {
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
    // The /config endpoint returns different responses based on authentication:
    // - Authenticated: Full ConfigResponse with all settings
    // - Unauthenticated: PublicConfigResponse with limited settings
    const response = await api.get<ConfigResponseType>(`${getURL("CONFIG")}`);
    const data = response["data"];
    if (data) {
      // Set timeout (present in both response types)
      const timeoutInMilliseconds = data.frontend_timeout
        ? data.frontend_timeout * 1000
        : DEFAULT_TIMEOUT;
      axios.defaults.baseURL = "";
      axios.defaults.timeout = timeoutInMilliseconds;

      // Set fields present in both public and full config
      setMaxFileSizeUpload(data.max_file_size_upload);
      setEventDelivery(data.event_delivery ?? EventDeliveryType.POLLING);

      // Set authenticated-only fields if present (full config)
      if (isFullConfig(data)) {
        setAutoSaving(data.auto_saving);
        setAutoSavingInterval(data.auto_saving_interval);
        setHealthCheckMaxRetries(data.health_check_max_retries);
        setFeatureFlags(data.feature_flags);
        setSerializationMaxItemsLength(data.serialization_max_items_length);
        setWebhookPollingInterval(
          data.webhook_polling_interval ?? DEFAULT_POLLING_INTERVAL,
        );
        setWebhookAuthEnable(data.webhook_auth_enable ?? true);
        setDefaultFolderName(data.default_folder_name ?? "Starter Project");
        setHideGettingStartedProgress(
          data.hide_getting_started_progress ?? false,
        );
      }
    }
    return data;
  };

  const queryResult = query(["useGetConfig"], getConfigFn, {
    refetchOnWindowFocus: false,
    ...options,
  });

  return queryResult;
};
