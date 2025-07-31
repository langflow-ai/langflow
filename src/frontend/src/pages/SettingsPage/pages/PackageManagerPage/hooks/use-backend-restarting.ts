import { QueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

const useBackendRestarting = (
  showProgressDialog: boolean,
  setIsBackendRestarting: (value: boolean) => void,
  setRestartDetectedAt: (value: number | null) => void,
  backendHealth: { isError: boolean; isSuccess: boolean },
  isBackendRestarting: boolean,
  restartDetectedAt: number | null,
  queryClient: QueryClient,
) => {
  useEffect(() => {
    if (!showProgressDialog) {
      setIsBackendRestarting(false);
      setRestartDetectedAt(null);
      return;
    }
    if (backendHealth.isError && !isBackendRestarting) {
      console.log("Backend restart detected during package installation");
      setIsBackendRestarting(true);
      setRestartDetectedAt(Date.now());
    }

    if (backendHealth.isSuccess && isBackendRestarting && restartDetectedAt) {
      const restartDuration = Date.now() - restartDetectedAt;
      console.log(`Backend restart completed after ${restartDuration}ms`);

      setTimeout(() => {
        setIsBackendRestarting(false);
        setRestartDetectedAt(null);
        queryClient.invalidateQueries({ queryKey: ["installation-status"] });
      }, 2000);
    }
  }, [
    showProgressDialog,
    backendHealth.isError,
    backendHealth.isSuccess,
    isBackendRestarting,
    restartDetectedAt,
    setIsBackendRestarting,
    setRestartDetectedAt,
    queryClient,
  ]);
};

export default useBackendRestarting;
