import ShortUniqueId from "short-unique-id";
import {
  ALLOWED_IMAGE_INPUT_EXTENSIONS,
  FS_ERROR_TEXT,
  SN_ERROR_TEXT,
} from "../../../../../../constants/constants";
// import useFileUpload from "./use-file-upload";

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

  return {
    dragOver,
    dragEnter,
    dragLeave,
  };
};

export default useDragAndDrop;
