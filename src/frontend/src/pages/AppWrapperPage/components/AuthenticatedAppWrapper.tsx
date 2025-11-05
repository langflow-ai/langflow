import AlertDisplayArea from "@/alerts/displayArea";
import CrashErrorComponent from "@/components/common/crashErrorComponent";
import { LoadingPage } from "@/pages/LoadingPage";
import { Suspense } from "react";
import { ErrorBoundary } from "react-error-boundary";
import { Outlet } from "react-router-dom";
import { GenericErrorComponent } from "./GenericErrorComponent";
import { useHealthCheck } from "../hooks/use-health-check";

const ShellOutlet = () => {
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
          <Suspense fallback={<LoadingPage />}>
            <Outlet />
          </Suspense>
        </>
      </ErrorBoundary>
      <div className="app-div">
        <AlertDisplayArea />
      </div>
    </div>
  );
};

export function AuthenticatedAppWrapper() {
  return <ShellOutlet />;
}

export default AuthenticatedAppWrapper;