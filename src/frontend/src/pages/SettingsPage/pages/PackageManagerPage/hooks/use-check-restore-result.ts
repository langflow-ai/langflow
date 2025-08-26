import { QueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { InstallationStatus } from "@/controllers/API/queries/packages";
import { TEXTS } from "../helpers/installed-packages-table.constants";

const useCheckRestoreResult = (
  showProgressDialog: boolean,
  queryClient: QueryClient,
  installationResult: InstallationStatus["last_result"] | undefined,
  lastHandledError: string | null,
  setShowProgressDialog: (value: boolean) => void,
  setIsInstallingPackage: (value: boolean) => void,
  setSuccessData: (value: { title: string; list: string[] }) => void,
  setErrorData: (value: { title: string; list: string[] }) => void,
  setLastHandledError: (value: string | null) => void,
) => {
  useEffect(() => {
    if (lastHandledError?.includes(`restore-api-error`)) {
      return;
    }

    const isInstallationResultValid =
      showProgressDialog &&
      installationResult &&
      (installationResult.status === "completed" ||
        installationResult.status === "failed");

    if (isInstallationResultValid) {
      if (installationResult.package_name !== "langflow-restore") {
        return;
      }

      const errorKey = `langflow-restore-${installationResult.status}`;

      // Prevent duplicate notifications
      if (errorKey === lastHandledError) {
        return;
      }

      setShowProgressDialog(false);
      setIsInstallingPackage(false);
      setLastHandledError(errorKey);

      if (installationResult.status === "completed") {
        setSuccessData({
          title: TEXTS.RESTORE_SUCCESS_TITLE,
          list: [],
        });
        queryClient.invalidateQueries({ queryKey: ["installed-packages"] });
      } else if (installationResult.status === "failed") {
        const rawError = installationResult.message || TEXTS.UNKNOWN_ERROR;
        let cleanError = rawError;

        if (rawError.includes("sync failed")) {
          cleanError = TEXTS.RESTORE_SYNC_FAILED;
        } else if (rawError.includes("×")) {
          const lines = rawError.split("\n");
          const errorLine =
            lines.find((line) => line.includes("×")) || lines[0];
          cleanError = errorLine.replace(/^\s*×\s*/, "").trim();
        }

        setErrorData({
          title: TEXTS.RESTORE_FAILED,
          list: [cleanError],
        });
      }
    }
  }, [
    showProgressDialog,
    installationResult,
    lastHandledError,
    setErrorData,
    setSuccessData,
    setIsInstallingPackage,
    queryClient,
  ]);
};

export default useCheckRestoreResult;
