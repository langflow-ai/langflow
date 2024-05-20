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
    if (e.dataTransfer.types.some((type) => type === "Files")) {
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        const firstFile = e.dataTransfer.files[0];
        if (firstFile.type === "application/json") {
          uploadFormData(firstFile);
        } else {
          setErrorData({
            title: WRONG_FILE_ERROR_ALERT,
            list: [UPLOAD_ALERT_LIST],
          });
        }
      }
    }
  };

  const dragOver = (
    e:
      | React.DragEvent<HTMLDivElement>
      | React.DragEvent<HTMLButtonElement>
      | React.DragEvent<HTMLAnchorElement>
  ) => {
    e.preventDefault();
    if (e.dataTransfer.types.some((types) => types === "Files")) {
      setFolderDragging(true);
    }
  };

  const dragEnter = (
    e:
      | React.DragEvent<HTMLDivElement>
      | React.DragEvent<HTMLButtonElement>
      | React.DragEvent<HTMLAnchorElement>
  ) => {
    if (e.dataTransfer.types.some((types) => types === "Files")) {
      setFolderDragging(true);
    }
    e.preventDefault();
  };

  const dragLeave = (
    e:
      | React.DragEvent<HTMLDivElement>
      | React.DragEvent<HTMLButtonElement>
      | React.DragEvent<HTMLAnchorElement>
  ) => {
    e.preventDefault();
    if (e.target === e.currentTarget) {
      setFolderDragging(false);
    }
  };

  const onDrop = (
    e:
      | React.DragEvent<HTMLDivElement>
      | React.DragEvent<HTMLButtonElement>
      | React.DragEvent<HTMLAnchorElement>
  ) => {
    const data = JSON.parse(e.dataTransfer.getData("flow"));

    if (data) {
      uploadFormData(data);
      return;
    }

    e.preventDefault();
    handleFileDrop(e);
    setFolderDragging(false);
  };

  const uploadFormData = (data) => {
    const formData = new FormData();
    formData.append("file", data);

    uploadFlowsFromFolders(formData).then(() => {
      getFoldersApi(true);
    });

    triggerFolderChange(folderId);
  };

  return {
    dragOver,
    dragEnter,
    dragLeave,
    onDrop,
  };
};

export default useFileDrop;
