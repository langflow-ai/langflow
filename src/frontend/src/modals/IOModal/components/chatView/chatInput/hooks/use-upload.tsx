import { useEffect } from "react";
import { uploadFile } from "../../../../../../controllers/API";

const useUpload = (uploadFile, currentFlowId, setFiles, uid) => {
  useEffect(() => {
    const handlePaste = (event: ClipboardEvent): void => {
      const items = event.clipboardData?.items;
      if (items) {
        for (let i = 0; i < items.length; i++) {
          const type = items[0].type.split("/")[0];

          const blob = items[i].getAsFile();
          if (blob) {
            const id = uid();
            setFiles((prevFiles) => [
              ...prevFiles,
              { file: blob, loading: true, error: false, id, type },
            ]);

            uploadFiles(blob, currentFlowId, setFiles, id);
          }
        }
      }
    };

    document.addEventListener("paste", handlePaste);
    return () => {
      document.removeEventListener("paste", handlePaste);
    };
  }, [uploadFile, currentFlowId]);

  return null;
};

const uploadFiles = (blob, currentFlowId, setFiles, id) => {
  uploadFile(blob, currentFlowId)
    .then((res) => {
      setFiles((prev) => {
        const newFiles = [...prev];
        const updatedIndex = newFiles.findIndex((file) => file.id === id);
        newFiles[updatedIndex].loading = false;
        newFiles[updatedIndex].path = res.data.file_path;
        return newFiles;
      });
    })
    .catch(() => {
      setFiles((prev) => {
        const newFiles = [...prev];
        const updatedIndex = newFiles.findIndex((file) => file.id === id);
        newFiles[updatedIndex].loading = false;
        newFiles[updatedIndex].error = true;
        return newFiles;
      });
    });
};

export default useUpload;
