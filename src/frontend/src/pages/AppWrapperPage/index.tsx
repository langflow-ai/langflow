import AlertDisplayArea from "@/alerts/displayArea";
import CrashErrorComponent from "@/components/common/crashErrorComponent";
import { ErrorBoundary } from "react-error-boundary";
import useAuthStore from "@/stores/authStore";
import { Outlet , useLocation } from "react-router-dom";
import Landing from "../LandingPage";
import { GenericErrorComponent } from "./components/GenericErrorComponent";
import { useHealthCheck } from "./hooks/use-health-check";

export function AppWrapperPage() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const { pathname } = useLocation();
  const { healthCheckTimeout, fetchingHealth, refetch } = useHealthCheck();

  // Render the marketing landing page instead of the authenticated app shell
  // when a visitor hits the root route without an active session.
  if (!isAuthenticated && pathname === "/") {
    return <Landing />;
  }

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
