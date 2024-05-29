import ShortUniqueId from "short-unique-id";
import useFileUpload from "./use-file-upload";

const useDragAndDrop = (setIsDragging, setFiles, currentFlowId) => {
  const dragOver = (e) => {
    e.preventDefault();
    if (e.dataTransfer.types.some((type) => type === "Files")) {
      setIsDragging(true);
    }
  };

  const dragEnter = (e) => {
    if (e.dataTransfer.types.some((type) => type === "Files")) {
      setIsDragging(true);
    }
    e.preventDefault();
  };

  const dragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const onDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files, setFiles, currentFlowId);
      e.dataTransfer.clearData();
    }
    setIsDragging(false);
  };
  return {
    dragOver,
    dragEnter,
    dragLeave,
    onDrop,
  };
};

const handleFiles = (files, setFiles, currentFlowId) => {
  if (files) {
    const uid = new ShortUniqueId({ length: 3 });
    const id = uid();
    const type = files[0].type.split("/")[0];
    const blob = files[0];

    setFiles((prevFiles) => [
      ...prevFiles,
      { file: blob, loading: true, error: false, id, type },
    ]);

    useFileUpload(blob, currentFlowId, setFiles, id);
  }
};
export default useDragAndDrop;
