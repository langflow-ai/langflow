import { AxiosResponse } from "axios";
import { useEffect } from "react";
import ShortUniqueId from "short-unique-id";
import {
  ALLOWED_IMAGE_INPUT_EXTENSIONS,
  FS_ERROR_TEXT,
  SN_ERROR_TEXT,
} from "../../../../../../constants/constants";
import useAlertStore from "../../../../../../stores/alertStore";
import { UploadFileTypeAPI } from "../../../../../../types/api";

const useUpload = (
  uploadFile: (
    file: File,
    id: string,
  ) => Promise<AxiosResponse<UploadFileTypeAPI>>,
  currentFlowId: string,
  setFiles: any,
  lockChat: boolean,
) => {
  const setErrorData = useAlertStore((state) => state.setErrorData);
  useEffect(() => {
    const handlePaste = (event: ClipboardEvent): void => {
      if (lockChat) {
        return;
      }
      const items = event.clipboardData?.items;
      if (items) {
        for (let i = 0; i < items.length; i++) {
          const type = items[0].type.split("/")[0];
          const uid = new ShortUniqueId();
          const blob = items[i].getAsFile();
          if (blob) {
            const fileExtension = blob.name.split(".").pop()?.toLowerCase();

            if (
              !fileExtension ||
              !ALLOWED_IMAGE_INPUT_EXTENSIONS.includes(fileExtension)
            ) {
              setErrorData({
                title: "Error uploading file",
                list: [FS_ERROR_TEXT, SN_ERROR_TEXT],
              });
              return;
            }
            const id = uid.randomUUID(3);
            setFiles((prevFiles) => [
              ...prevFiles,
              { file: blob, loading: true, error: false, id, type },
            ]);
          }
        }
      }
    };

    document.addEventListener("paste", handlePaste);
    return () => {
      document.removeEventListener("paste", handlePaste);
    };
  }, [uploadFile, currentFlowId, lockChat]);

  return null;
};

export default useUpload;
