import AlertDisplayArea from "@/alerts/displayArea";
import CrashErrorComponent from "@/components/crashErrorComponent";
import FetchErrorComponent from "@/components/fetchErrorComponent";
import LoadingComponent from "@/components/loadingComponent";
import TimeoutErrorComponent from "@/components/timeoutErrorComponent";
import {
  FETCH_ERROR_DESCRIPION,
  FETCH_ERROR_MESSAGE,
  TIMEOUT_ERROR_DESCRIPION,
  TIMEOUT_ERROR_MESSAGE,
} from "@/constants/constants";
import { useGetHealthQuery } from "@/controllers/API/queries/health";
import useTrackLastVisitedPath from "@/hooks/use-track-last-visited-path";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { cn } from "@/utils/utils";
import { AxiosError } from "axios";
import { useEffect, useMemo, useState } from "react";
import { ErrorBoundary } from "react-error-boundary";
import { Outlet } from "react-router-dom";

export function AppWrapperPage() {
  useTrackLastVisitedPath();

  const isLoading = useFlowsManagerStore((state) => state.isLoading);

  const healthCheckMaxRetries = useFlowsManagerStore(
    (state) => state.healthCheckMaxRetries,
  );

  const healthCheckTimeout = useUtilityStore(
    (state) => state.healthCheckTimeout,
  );

  const {
    data: healthData,
    isFetching: fetchingHealth,
    isError: isErrorHealth,
    error,
    refetch,
  } = useGetHealthQuery();

  const isServerDown =
    isErrorHealth ||
    (healthData && Object.values(healthData).some((value) => value !== "ok")) ||
    healthCheckTimeout === "serverDown";

  const isTimeoutResponseServer = healthCheckTimeout === "timeout";

  const [retryCount, setRetryCount] = useState(0);

  console.log(healthCheckMaxRetries);

  useEffect(() => {
    const isServerBusy =
      (error as AxiosError)?.response?.status === 503 ||
      (error as AxiosError)?.response?.status === 429;

    if (isServerBusy && isErrorHealth) {
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
  }, [isErrorHealth, retryCount, refetch]);

  const modalErrorComponent = useMemo(() => {
    switch (healthCheckTimeout) {
      case "serverDown":
        return (
          <FetchErrorComponent
            description={FETCH_ERROR_DESCRIPION}
            message={FETCH_ERROR_MESSAGE}
            openModal={isServerDown}
            setRetry={() => {
              refetch();
            }}
            isLoadingHealth={fetchingHealth}
          ></FetchErrorComponent>
        );
      case "timeout":
        return (
          <TimeoutErrorComponent
            description={TIMEOUT_ERROR_MESSAGE}
            message={TIMEOUT_ERROR_DESCRIPION}
            openModal={isTimeoutResponseServer}
            setRetry={() => {
              refetch();
            }}
            isLoadingHealth={fetchingHealth}
          ></TimeoutErrorComponent>
        );
      default:
        return null;
    }
  }, [healthCheckTimeout, fetchingHealth]);

  return (
    <div className="flex h-full flex-col">
      <ErrorBoundary
        onReset={() => {
          // any reset function
        }}
        FallbackComponent={CrashErrorComponent}
      >
        <>
          {modalErrorComponent}

          <div
            className={cn(
              "loading-page-panel absolute left-0 top-0 z-[999]",
              isLoading ? "" : "hidden",
            )}
          >
            <LoadingComponent remSize={50} />
          </div>
          <Outlet />
        </>
      </ErrorBoundary>
      <div></div>
      <div className="app-div">
        <AlertDisplayArea />
      </div>
    </div>
  );
}
