import type { DragEvent } from "react";
import { useCallback, useEffect, useRef } from "react";
import useUploadFlow from "@/hooks/flows/use-upload-flow";
import {
  getFlowFilesFromClipboard,
  getPastedFlowFile,
  isEditablePasteTarget,
} from "@/utils/pasteFlowImport";
import { CONSOLE_ERROR_MSG } from "../../../constants/alerts_constants";
import useAlertStore from "../../../stores/alertStore";

const useFileDrop = (type?: string) => {
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const uploadFlow = useUploadFlow();

  const lastUploadTime = useRef<number>(0);
  const DEBOUNCE_INTERVAL = 1000;

  const uploadFiles = useCallback(
    (files: File[]) => {
      const currentTime = Date.now();
      if (currentTime - lastUploadTime.current < DEBOUNCE_INTERVAL) return;
      lastUploadTime.current = currentTime;

      uploadFlow({
        files,
        isComponent:
          type === "components" ? true : type === "flows" ? false : undefined,
      })
        .then(() => {
          setSuccessData({
            title: "All files uploaded successfully",
          });
        })
        .catch((error) => {
          console.error(error);
          setErrorData({
            title: CONSOLE_ERROR_MSG,
            list: [(error as Error).message],
          });
        });
    },
    [type, uploadFlow, setSuccessData, setErrorData],
  );

  const handleFileDrop = useCallback(
    (e: DragEvent<HTMLElement>) => {
      e.preventDefault();
      if (e.dataTransfer?.types?.every((t) => t === "Files")) {
        const files: File[] = Array.from(e.dataTransfer.files);
        uploadFiles(files);
      }
    },
    [uploadFiles],
  );

  useEffect(() => {
    const handlePaste = (event: ClipboardEvent) => {
      if (type === "mcp") return;
      if (isEditablePasteTarget(event.target)) return;

      const pastedFiles = getFlowFilesFromClipboard(event.clipboardData);
      if (pastedFiles.length > 0) {
        event.preventDefault();
        event.stopPropagation();
        uploadFiles(pastedFiles);
        return;
      }

      const rawText =
        event.clipboardData?.getData("text/plain") ??
        event.clipboardData?.getData("text") ??
        "";
      const file = getPastedFlowFile(rawText);
      if (!file) return;

      event.preventDefault();
      event.stopPropagation();
      uploadFiles([file]);
    };

    document.addEventListener("paste", handlePaste, true);
    return () => {
      document.removeEventListener("paste", handlePaste, true);
    };
  }, [type, uploadFiles]);

  return handleFileDrop;
};

export default useFileDrop;
