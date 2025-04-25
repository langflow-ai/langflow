import AlertDisplayArea from "@/alerts/displayArea";
import CrashErrorComponent from "@/components/common/crashErrorComponent";
import { ErrorBoundary } from "react-error-boundary";
import { Outlet } from "react-router-dom";
import { GenericErrorComponent } from "./components/GenericErrorComponent";
import { useHealthCheck } from "./hooks/use-health-check";

export function AppWrapperPage() {
  const { healthCheckTimeout, fetchingHealth, refetch } = useHealthCheck();

  return (
    <div className="flex h-full w-full flex-col">
      <ErrorBoundary
        onReset={() => {
          // any reset function
        }}
        FallbackComponent={CrashErrorComponent}
      >
        <>
          <GenericErrorComponent
            healthCheckTimeout={healthCheckTimeout}
            fetching={fetchingHealth}
            retry={refetch}
          />
          <Outlet />
        </>
      </ErrorBoundary>
      <div className="app-div">
        <AlertDisplayArea />
      </div>
    </div>
  );
}
