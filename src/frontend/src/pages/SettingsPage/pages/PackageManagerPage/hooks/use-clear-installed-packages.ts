import { QueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { InstallationStatus } from "@/controllers/API/queries/packages";
import { TEXTS } from "../helpers/installed-packages-table.constants";

const useClearInstalledPackages = (
  showProgressDialog: boolean,
  backendHealth: { isSuccess: boolean; isFetched: boolean },
  queryClient: QueryClient,
  installationResult: InstallationStatus["last_result"] | undefined,
  setShowProgressDialog: (value: boolean) => void,
  setIsInstallingPackage: (value: boolean) => void,
  setSuccessData: (value: { title: string; list: string[] }) => void,
) => {
  useEffect(() => {
    if (!showProgressDialog) return;

    if (backendHealth.isSuccess && backendHealth.isFetched) {
      const timeoutId = setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["installation-status"] });

        if (!installationResult) {
          setShowProgressDialog(false);
          setIsInstallingPackage(false);
          setSuccessData({
            title: TEXTS.RESTORE_SUCCESS_TITLE,
            list: [],
          });
          queryClient.invalidateQueries({ queryKey: ["installed-packages"] });
        }
      }, 3000);

      return () => clearTimeout(timeoutId);
    }
  }, [
    showProgressDialog,
    backendHealth.isSuccess,
    backendHealth.isFetched,
    installationResult,
    queryClient,
    setSuccessData,
    setIsInstallingPackage,
  ]);
};

export default useClearInstalledPackages;
