import { useGetHealthQuery } from "@/controllers/API/queries/health";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { AxiosError } from "axios";
import { useEffect, useState } from "react";

export function useHealthCheck({ disabled }) {
  const healthCheckMaxRetries = useFlowsManagerStore(
    (state) => state.healthCheckMaxRetries,
  );

  const healthCheckTimeout = useUtilityStore(
    (state) => state.healthCheckTimeout,
  );

  const {
    isFetching: fetchingHealth,
    isError: isErrorHealth,
    error,
    refetch,
  } = useGetHealthQuery({ enabled: !disabled });

  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    const isServerBusy =
      (error as AxiosError)?.response?.status === 503 ||
      (error as AxiosError)?.response?.status === 429;

    if (isServerBusy && isErrorHealth && !disabled) {
      const maxRetries = healthCheckMaxRetries;
      if (retryCount < maxRetries) {
        const delay = Math.pow(2, retryCount) * 1000;
        const timer = setTimeout(() => {
          refetch();
          setRetryCount(retryCount + 1);
        }, delay);

        return () => clearTimeout(timer);
      }
    } else {
      setRetryCount(0);
    }
  }, [isErrorHealth, retryCount, refetch, disabled]);

  return { healthCheckTimeout, refetch, fetchingHealth };
}
