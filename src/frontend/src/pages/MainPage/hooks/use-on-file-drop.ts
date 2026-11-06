import { useCallback, useRef } from "react";
import { useTranslation } from "react-i18next";
import useUploadFlow from "@/hooks/flows/use-upload-flow";
import { extractApiErrorMessages } from "@/utils/apiError";
import useAlertStore from "../../../stores/alertStore";

const useFileDrop = (type?: string) => {
  const { t } = useTranslation();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const uploadFlow = useUploadFlow();

  const lastUploadTime = useRef<number>(0);
  const DEBOUNCE_INTERVAL = 1000;

  const handleFileDrop = useCallback(
    (e) => {
      e.preventDefault();

      if (e.dataTransfer.types.every((type) => type === "Files")) {
        const currentTime = Date.now();

        if (currentTime - lastUploadTime.current >= DEBOUNCE_INTERVAL) {
          lastUploadTime.current = currentTime;

          const files: File[] = Array.from(e.dataTransfer.files);

          uploadFlow({
            files,
            isComponent:
              type === "components"
                ? true
                : type === "flows"
                  ? false
                  : undefined,
          })
            .then(() => {
              setSuccessData({
                title: `All files uploaded successfully`,
              });
            })
            .catch((error) => {
              setErrorData({
                title: t("errors.uploadFile"),
                list: extractApiErrorMessages(error),
              });
            });
        }
      }
    },
    [type, uploadFlow, setSuccessData, setErrorData],
  );

  return handleFileDrop;
};

export default useFileDrop;
