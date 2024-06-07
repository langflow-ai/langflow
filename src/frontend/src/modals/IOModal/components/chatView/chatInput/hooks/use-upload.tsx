import { useEffect } from "react";
import ShortUniqueId from "short-unique-id";
import useFileUpload from "./use-file-upload";

const useUpload = (uploadFile, currentFlowId, setFiles, lockChat) => {
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
