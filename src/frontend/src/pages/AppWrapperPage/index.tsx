import AlertDisplayArea from "@/alerts/displayArea";
import CrashErrorComponent from "@/components/crashErrorComponent";
import { CustomHeader } from "@/customization/components/custom-header";
import { useCustomHealthCheck } from "@/customization/hooks/use-custom-health-check";
import { ErrorBoundary } from "react-error-boundary";
import { Outlet } from "react-router-dom";
import { GenericErrorComponent } from "./components/GenericErrorComponent";
import { useHealthCheck } from "./hooks/use-health-check";

export function AppWrapperPage() {
  const { message, description, isFetching, isError } = useCustomHealthCheck();
  const { healthCheckTimeout, fetchingHealth, refetch } = useHealthCheck({
    disabled: isFetching || isError,
  });

  return (
    <div className="flex h-full flex-col">
      <CustomHeader />
      <ErrorBoundary
        onReset={() => {
          // any reset function
        }}
        FallbackComponent={CrashErrorComponent}
      >
        <>
          <GenericErrorComponent
            healthCheckTimeout={isError ? "custom" : healthCheckTimeout}
            fetching={isFetching || fetchingHealth}
            description={description}
            message={message}
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
