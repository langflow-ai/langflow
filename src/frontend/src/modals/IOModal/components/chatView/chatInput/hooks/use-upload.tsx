import { useEffect } from "react";
import ShortUniqueId from "short-unique-id";
import useAlertStore from "../../../../../../stores/alertStore";
import useFileUpload from "./use-file-upload";

const fsErrorText =
  "Please ensure your file has one of the following extensions:";
const snErrorTxt = "png, jpg, jpeg";

const useUpload = (uploadFile, currentFlowId, setFiles, lockChat) => {
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
          const uid = new ShortUniqueId({ length: 3 });
          const blob = items[i].getAsFile();
          if (blob) {
            const allowedExtensions = ["png", "jpg", "jpeg"];
            const fileExtension = blob.name.split(".").pop()?.toLowerCase();

            if (!fileExtension || !allowedExtensions.includes(fileExtension)) {
              setErrorData({
                title: "Error uploading file",
                list: [fsErrorText, snErrorTxt],
              });
              return;
            }
            const id = uid();
            setFiles((prevFiles) => [
              ...prevFiles,
              { file: blob, loading: true, error: false, id, type },
            ]);
            useFileUpload(blob, currentFlowId, setFiles, id);
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
