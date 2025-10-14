import { keepPreviousData } from "@tanstack/react-query";
import type { AxiosError } from "axios";
import {
  REFETCH_SERVER_HEALTH_INTERVAL,
  SERVER_HEALTH_INTERVAL,
} from "@/constants/constants";
import { HEALTH_CHECK_URL } from "@/customization/config-constants";
import { useUtilityStore } from "@/stores/utilityStore";
import { createNewError503 } from "@/types/factory/axios-error-503";
import type { useQueryFunctionType } from "../../../../types/api";
import { UseRequestProcessor } from "../../services/request-processor";

interface getHealthResponse {
  status: string;
  chat: string;
  db: string;
  folder: string;
  variables: string;
}

interface getHealthParams {
  enableInterval?: boolean;
}

export const useGetHealthQuery: useQueryFunctionType<
  getHealthParams,
  getHealthResponse
> = (params, options) => {
  const { query } = UseRequestProcessor();
  const setHealthCheckTimeout = useUtilityStore(
    (state) => state.setHealthCheckTimeout,
  );
  const healthCheckTimeout = useUtilityStore(
    (state) => state.healthCheckTimeout,
  );
  /**
   * Fetches the health status of the API.
   *
   * @returns {Promise<AxiosResponse<TransactionsResponse>>} A promise that resolves to an AxiosResponse containing the health status.
   */
  async function getHealthFn() {
    // Disable actual network health checks; return a static OK
    const staticOk: getHealthResponse = {
      status: "ok",
      chat: "ok",
      db: "ok",
      folder: "ok",
      variables: "ok",
    };
    setHealthCheckTimeout(null);
    return staticOk;
  }

  const queryResult = query(["useGetHealthQuery"], getHealthFn, {
    placeholderData: keepPreviousData,
    // Fully disable refetch interval to stop intermittent calls
    refetchInterval: false,
    retry: false,
    refetchOnWindowFocus: false,
    ...options,
  });

  return queryResult;
};
