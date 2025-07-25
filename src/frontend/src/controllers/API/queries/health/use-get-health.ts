import { keepPreviousData } from "@tanstack/react-query";
import type { AxiosError } from "axios";
import {
  REFETCH_SERVER_HEALTH_INTERVAL,
  SERVER_HEALTH_INTERVAL,
} from "@/constants/constants";
import { HEALTH_CHECK_URL } from "@/customization/config-constants";
import { usePackageManagerStore } from "@/stores/packageManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { createNewError503 } from "@/types/factory/axios-error-503";
import type { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
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
  const isInstallingPackage = usePackageManagerStore(
    (state) => state.isInstallingPackage,
  );
  /**
   * Fetches the health status of the API.
   *
   * @returns {Promise<AxiosResponse<TransactionsResponse>>} A promise that resolves to an AxiosResponse containing the health status.
   */
  async function getHealthFn() {
    try {
      const timeoutPromise = new Promise<never>((_, reject) =>
        setTimeout(() => reject(createNewError503()), SERVER_HEALTH_INTERVAL),
      );

      const apiPromise = api.get<getHealthResponse>(
        HEALTH_CHECK_URL || "/health",
      );
      const response = await Promise.race([apiPromise, timeoutPromise]);
      setHealthCheckTimeout(
        Object.values(response.data).some((value) => value !== "ok")
          ? "serverDown"
          : null,
      );
      return response.data;
    } catch (error) {
      const isServerBusy =
        healthCheckTimeout === null &&
        (error as AxiosError)?.response?.status === 503;

      // Don't show timeout dialog if we're installing a package
      if (isServerBusy && !isInstallingPackage) {
        setHealthCheckTimeout("timeout");
      } else if (healthCheckTimeout === null && !isInstallingPackage) {
        setHealthCheckTimeout("serverDown");
      }
      throw error;
    }
  }

  const queryResult = query(["useGetHealthQuery"], getHealthFn, {
    placeholderData: keepPreviousData,
    refetchInterval: params.enableInterval
      ? REFETCH_SERVER_HEALTH_INTERVAL
      : false,
    retry: false,
    refetchOnWindowFocus: false,
    ...options,
  });

  return queryResult;
};
