import { useCallback } from "react";
import { getAxiosErrorMessage } from "@/controllers/API/helpers/get-axios-error-message";
import useAlertStore from "@/stores/alertStore";

export function useErrorAlert() {
  const setErrorData = useAlertStore((s) => s.setErrorData);
  return useCallback(
    (title: string, err: unknown) => {
      setErrorData({ title, list: [getAxiosErrorMessage(err)] });
    },
    [setErrorData],
  );
}
