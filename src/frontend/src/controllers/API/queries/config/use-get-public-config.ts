import axios from "axios";
import { DEFAULT_TIMEOUT } from "@/constants/constants";
import { EventDeliveryType } from "@/constants/enums";
import { useUtilityStore } from "@/stores/utilityStore";
import type { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface PublicConfigResponse {
  frontend_timeout: number;
  max_file_size_upload: number;
  event_delivery: EventDeliveryType;
  voice_mode_available: boolean;
}

export const useGetPublicConfig: useQueryFunctionType<
  undefined,
  PublicConfigResponse
> = (options) => {
  const setMaxFileSizeUpload = useUtilityStore(
    (state) => state.setMaxFileSizeUpload,
  );
  const setEventDelivery = useUtilityStore((state) => state.setEventDelivery);

  const { query } = UseRequestProcessor();

  const getPublicConfigFn = async () => {
    const response = await api.get<PublicConfigResponse>(
      `${getURL("PUBLIC_CONFIG")}`,
    );
    const data = response["data"];
    if (data) {
      const timeoutInMilliseconds = data.frontend_timeout
        ? data.frontend_timeout * 1000
        : DEFAULT_TIMEOUT;
      axios.defaults.baseURL = "";
      axios.defaults.timeout = timeoutInMilliseconds;
      setMaxFileSizeUpload(data.max_file_size_upload);
      setEventDelivery(data.event_delivery ?? EventDeliveryType.POLLING);
    }
    return data;
  };

  const queryResult = query(["useGetPublicConfig"], getPublicConfigFn, {
    refetchOnWindowFocus: false,
    retry: false, // Don't retry on failure for public config
    ...options,
  });

  return queryResult;
};
