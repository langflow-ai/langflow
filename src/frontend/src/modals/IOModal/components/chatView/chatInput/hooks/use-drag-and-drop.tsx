import ShortUniqueId from "short-unique-id";
import {
  ALLOWED_IMAGE_INPUT_EXTENSIONS,
  FS_ERROR_TEXT,
  SN_ERROR_TEXT,
} from "../../../../../../constants/constants";
import useFileUpload from "./use-file-upload";

const useDragAndDrop = (
  setIsDragging: (value: boolean) => void,
  setFiles: (value: any) => void,
  currentFlowId: string,
  setErrorData: (value: any) => void,
) => {
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
      handleFiles(e.dataTransfer.files, setFiles, currentFlowId, setErrorData);
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

const handleFiles = (files, setFiles, currentFlowId, setErrorData) => {
  if (files) {
    const file = files?.[0];
    const fileExtension = file.name.split(".").pop()?.toLowerCase();
    if (
      !fileExtension ||
      !ALLOWED_IMAGE_INPUT_EXTENSIONS.includes(fileExtension)
    ) {
      console.log("Error uploading file");
      setErrorData({
        title: "Error uploading file",
        list: [FS_ERROR_TEXT, SN_ERROR_TEXT],
      });
      return;
    }
    const uid = new ShortUniqueId();
    const id = uid.randomUUID(3);
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
