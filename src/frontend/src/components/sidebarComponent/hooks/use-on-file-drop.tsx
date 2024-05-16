import {
  CONSOLE_ERROR_MSG,
  UPLOAD_ALERT_LIST,
  WRONG_FILE_ERROR_ALERT,
} from "../../../constants/alerts_constants";
import useAlertStore from "../../../stores/alertStore";
import useFlowsManagerStore from "../../../stores/flowsManagerStore";
import { useFolderStore } from "../../../stores/foldersStore";

const useFileDrop = (folderId, is_component, folderChangeCallback) => {
  const folderDragging = useFolderStore((state) => state.folderDragging);
  const setFolderDragging = useFolderStore((state) => state.setFolderDragging);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const uploadFlow = useFlowsManagerStore((state) => state.uploadFlow);

  const triggerFolderChange = (folderId) => {
    if (folderChangeCallback) {
      folderChangeCallback(folderId);
    }
  };

  const handleFileDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.types.some((type) => type === "Files")) {
      if (e.dataTransfer.files.item(0).type === "application/json") {
        uploadFlow({
          newProject: true,
          file: e.dataTransfer.files.item(0),
          isComponent: is_component,
        })
          .then(() => {
            triggerFolderChange(folderId);
          })
          .catch((error) => {
            setErrorData({
              title: CONSOLE_ERROR_MSG,
              list: [error],
            });
          });
      } else {
        setErrorData({
          title: WRONG_FILE_ERROR_ALERT,
          list: [UPLOAD_ALERT_LIST],
        });
      }
    }
  };

  const dragOver = (e, folderId) => {
    console.log("dragOver");

    e.preventDefault();
    if (e.dataTransfer.types.some((types) => types === "Files")) {
      setFolderDragging(folderId);
    }
  };

  const dragEnter = (e, folderId) => {
    console.log("dragEnter");

    if (e.dataTransfer.types.some((types) => types === "Files")) {
      setFolderDragging(folderId);
    }
    e.preventDefault();
  };

  const dragLeave = (e) => {
    e.preventDefault();
    if (e.target === e.currentTarget) {
      setFolderDragging("");
    }
  };

  const onDrop = (e) => {
    console.log("onDrop");
    e.preventDefault();
    handleFileDrop(e);
    setFolderDragging("");
  };
  return {
    folderDragging,
    dragOver,
    dragEnter,
    dragLeave,
    onDrop,
  };
};

export default useFileDrop;
