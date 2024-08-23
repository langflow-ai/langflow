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
import { useMemo } from "react";
import { ErrorBoundary } from "react-error-boundary";
import { Outlet } from "react-router-dom";

export function AppWrapperPage() {
  useTrackLastVisitedPath();

  const isLoading = useFlowsManagerStore((state) => state.isLoading);

  const healthCheckTimeout = useUtilityStore(
    (state) => state.healthCheckTimeout,
  );

  const {
    data: healthData,
    isFetching: fetchingHealth,
    isError: isErrorHealth,
    refetch,
  } = useGetHealthQuery();

  const isUnhealthyServer =
    isErrorHealth ||
    (healthData && Object.values(healthData).some((value) => value !== "ok")) ||
    healthCheckTimeout === "unhealthy";

  const isTimeoutResponseServer = healthCheckTimeout === "timeout";

  const modalErrorComponent = useMemo(() => {
    switch (healthCheckTimeout) {
      case "unhealthy":
        return (
          <FetchErrorComponent
            description={FETCH_ERROR_DESCRIPION}
            message={FETCH_ERROR_MESSAGE}
            openModal={isUnhealthyServer}
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
