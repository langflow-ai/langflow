import { QueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { InstallationStatus } from "@/controllers/API/queries/packages";
import { TEXTS } from "../helpers/constants";

const useCheckInstallationResult = (
  showProgressDialog: boolean,
  queryClient: QueryClient,
  installationResult: InstallationStatus["last_result"] | undefined,
  packageName: string,
  lastHandledError: string | null,
  setSuccessData: (value: { title: string; list: string[] }) => void,
  setErrorData: (value: { title: string; list: string[] }) => void,
  setShowProgressDialog: (value: boolean) => void,
  setIsInstallingPackage: (value: boolean) => void,
  setPackageName: (value: string) => void,
  setLastHandledError: (value: string | null) => void,
) => {
  useEffect(() => {
    const isInstallationResultValid =
      showProgressDialog &&
      installationResult &&
      (installationResult.status === "completed" ||
        installationResult.status === "failed");

    if (isInstallationResultValid) {
      if (installationResult.package_name !== packageName.trim()) {
        return;
      }

      const errorKey = `${installationResult.package_name}-${installationResult.status}`;

      if (errorKey === lastHandledError) {
        return;
      }

      setShowProgressDialog(false);
      setIsInstallingPackage(false);
      setLastHandledError(errorKey);

      if (installationResult.status === "completed") {
        setSuccessData({
          title: TEXTS.PACKAGE_INSTALLED_SUCCESS(
            installationResult.package_name,
          ),
          list: [],
        });
        queryClient.invalidateQueries({ queryKey: ["installed-packages"] });
      } else if (installationResult.status === "failed") {
        const rawError = installationResult.message || TEXTS.UNKNOWN_ERROR;
        let cleanError = rawError;

        if (
          rawError.includes("No solution found when resolving dependencies")
        ) {
          const pkgName = installationResult.package_name || "package";
          if (rawError.includes("requires-python")) {
            cleanError = TEXTS.PYTHON_VERSION_ERROR(pkgName);
          } else {
            cleanError = TEXTS.DEPENDENCY_CONFLICT_ERROR(pkgName);
          }
        } else if (rawError.includes("×")) {
          const lines = rawError.split("\n");
          const errorLine =
            lines.find((line) => line.includes("×")) || lines[0];
          cleanError = errorLine.replace(/^\s*×\s*/, "").trim();
        }

        setErrorData({
          title: TEXTS.INSTALLATION_FAILED,
          list: [cleanError],
        });
      }
      setPackageName("");
    }
  }, [
    showProgressDialog,
    installationResult,
    packageName,
    lastHandledError,
    setErrorData,
    setSuccessData,
    setIsInstallingPackage,
    queryClient,
  ]);
};

export default useCheckInstallationResult;
