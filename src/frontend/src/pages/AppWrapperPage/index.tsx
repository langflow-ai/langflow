import AlertDisplayArea from "@/alerts/displayArea";
import CrashErrorComponent from "@/components/common/crashErrorComponent";
import MCPNoticeModal from "@/modals/mcpNoticeModal";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useEffect, useState } from "react";
import { ErrorBoundary } from "react-error-boundary";
import { Outlet } from "react-router-dom";
import { GenericErrorComponent } from "./components/GenericErrorComponent";
import { useHealthCheck } from "./hooks/use-health-check";

export function AppWrapperPage() {
  const { healthCheckTimeout, fetchingHealth, refetch } = useHealthCheck();
  const [showMCPModal, setShowMCPModal] = useState(false);
  const flows = useFlowsManagerStore((state) => state.flows);
  const hasSeenMCPModal = localStorage.getItem("hasSeenMCPModal");

  useEffect(() => {
    // Show modal if user has multiple flows and hasn't seen it before
    if (!hasSeenMCPModal && flows && flows.length > 1) {
      setShowMCPModal(true);
      // Mark as seen
      setTimeout(() => {
        localStorage.setItem("hasSeenMCPModal", "true");
      }, 1000);
    }
  }, [flows]);

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
        {!hasSeenMCPModal && (
          <MCPNoticeModal open={showMCPModal} setOpen={setShowMCPModal} />
        )}
      </div>
    </div>
  );
}
