import { QueryClient, UseMutationResult } from "@tanstack/react-query";
import { AxiosError } from "axios";
import { useEffect } from "react";
import {
  InstallationStatus,
  RestoreLangflowRequest,
  RestoreLangflowResponse,
} from "@/controllers/API/queries/packages";
import { TEXTS } from "../helpers/installed-packages-table.constants";

const useRestoreApiError = (
  showProgressDialog: boolean,
  restoreLangflowMutation,
  setShowProgressDialog: (value: boolean) => void,
  setIsInstallingPackage: (value: boolean) => void,
  setErrorData: (value: { title: string; list: string[] }) => void,
  setLastHandledError: (value: string | null) => void,
  lastHandledError: string | null,
) => {
  useEffect(() => {
    if (showProgressDialog && restoreLangflowMutation.isError) {
      const errorKey = `restore-api-error`;

      if (lastHandledError === errorKey) {
        return;
      }

      setShowProgressDialog(false);
      setIsInstallingPackage(false);
      const error = restoreLangflowMutation.error as any;
      const errorMessage =
        error?.response?.data?.detail || error?.message || TEXTS.UNKNOWN_ERROR;

      setErrorData({
        title: TEXTS.RESTORE_FAILED,
        list: [
          errorMessage.length > 200
            ? errorMessage.substring(0, 200) + "..."
            : errorMessage,
        ],
      });

      setLastHandledError(errorKey);
    }
  }, [
    showProgressDialog,
    restoreLangflowMutation.isError,
    restoreLangflowMutation.error,
    setErrorData,
    setIsInstallingPackage,
    lastHandledError,
  ]);
};

export default useRestoreApiError;
