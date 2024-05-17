import {
  UPLOAD_ALERT_LIST,
  WRONG_FILE_ERROR_ALERT,
} from "../../../constants/alerts_constants";
import { uploadFlowsFromFolders } from "../../../pages/MainPage/services";
import useAlertStore from "../../../stores/alertStore";
import { useFolderStore } from "../../../stores/foldersStore";

const useFileDrop = (folderId, is_component, folderChangeCallback) => {
  const setFolderDragging = useFolderStore((state) => state.setFolderDragging);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const getFoldersApi = useFolderStore((state) => state.getFoldersApi);
  const triggerFolderChange = (folderId) => {
    if (folderChangeCallback) {
      folderChangeCallback(folderId);
    }
  };
  const handleFileDrop = async (e) => {
    e.preventDefault();
    if (e.dataTransfer.types.some((type) => type === "Files")) {
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        const firstFile = e.dataTransfer.files[0];
        if (firstFile.type === "application/json") {
          const formData = new FormData();
          formData.append("file", firstFile);
          uploadFlowsFromFolders(formData).then(() => {
            getFoldersApi(true);
          });

          triggerFolderChange(folderId);
        } else {
          setErrorData({
            title: WRONG_FILE_ERROR_ALERT,
            list: [UPLOAD_ALERT_LIST],
          });
        }
      }
    }
  };

  const dragOver = (e) => {
    e.preventDefault();
    if (e.dataTransfer.types.some((types) => types === "Files")) {
      setFolderDragging(true);
    }
  };

  const dragEnter = (e) => {
    if (e.dataTransfer.types.some((types) => types === "Files")) {
      setFolderDragging(true);
    }
    e.preventDefault();
  };

  const dragLeave = (e) => {
    e.preventDefault();
    if (e.target === e.currentTarget) {
      setFolderDragging(false);
    }
  };

  const onDrop = (e) => {
    e.preventDefault();
    handleFileDrop(e);
    setFolderDragging(false);
  };
  return {
    dragOver,
    dragEnter,
    dragLeave,
    onDrop,
  };
};

export default useFileDrop;
