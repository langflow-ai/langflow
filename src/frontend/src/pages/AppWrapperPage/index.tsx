import AlertDisplayArea from "@/alerts/displayArea";
import CrashErrorComponent from "@/components/crashErrorComponent";
import FetchErrorComponent from "@/components/fetchErrorComponent";
import LoadingComponent from "@/components/loadingComponent";
import {
  FETCH_ERROR_DESCRIPION,
  FETCH_ERROR_MESSAGE,
} from "@/constants/constants";
import { useGetHealthQuery } from "@/controllers/API/queries/health";
import useTrackLastVisitedPath from "@/hooks/use-track-last-visited-path";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { cn } from "@/utils/utils";
import { ErrorBoundary } from "react-error-boundary";
import { Outlet } from "react-router-dom";

export function AppWrapperPage() {
  useTrackLastVisitedPath();

  const isLoading = useFlowsManagerStore((state) => state.isLoading);
  const {
    data: healthData,
    isFetching: fetchingHealth,
    isError: isErrorHealth,
    refetch,
  } = useGetHealthQuery();
  return (
    <div className="flex h-full flex-col">
      <ErrorBoundary
        onReset={() => {
          // any reset function
        }}
        FallbackComponent={CrashErrorComponent}
      >
        <>
          {
            <FetchErrorComponent
              description={FETCH_ERROR_DESCRIPION}
              message={FETCH_ERROR_MESSAGE}
              openModal={
                isErrorHealth ||
                (healthData &&
                  Object.values(healthData).some((value) => value !== "ok"))
              }
              setRetry={() => {
                refetch();
              }}
              isLoadingHealth={fetchingHealth}
            ></FetchErrorComponent>
          }

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
