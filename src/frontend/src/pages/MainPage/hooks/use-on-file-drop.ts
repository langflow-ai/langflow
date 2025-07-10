import { useCallback, useRef } from "react";
import useUploadFlow from "@/hooks/flows/use-upload-flow";
import { CONSOLE_ERROR_MSG } from "../../../constants/alerts_constants";
import useAlertStore from "../../../stores/alertStore";

const useFileDrop = (type?: string) => {
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
              console.log(error);
              setErrorData({
                title: CONSOLE_ERROR_MSG,
                list: [(error as Error).message],
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
