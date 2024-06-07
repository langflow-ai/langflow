import { uploadFile } from "../../../../../../controllers/API";

const useFileUpload = (blob, currentFlowId, setFiles, id) => {
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

  return null;
};

export default useFileUpload;
