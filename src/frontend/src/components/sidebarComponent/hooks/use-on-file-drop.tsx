import {
  UPLOAD_ALERT_LIST,
  WRONG_FILE_ERROR_ALERT,
} from "../../../constants/alerts_constants";
import { updateFlowInDatabase } from "../../../controllers/API";
import { uploadFlowsFromFolders } from "../../../pages/MainPage/services";
import useAlertStore from "../../../stores/alertStore";
import useFlowsManagerStore from "../../../stores/flowsManagerStore";
import { useFolderStore } from "../../../stores/foldersStore";
import { addVersionToDuplicates } from "../../../utils/reactflowUtils";

const useFileDrop = (
  folderId: string,
  folderChangeCallback: (folderId: string) => void,
) => {
  const setFolderDragging = useFolderStore((state) => state.setFolderDragging);
  const setFolderIdDragging = useFolderStore(
    (state) => state.setFolderIdDragging,
  );

  const setErrorData = useAlertStore((state) => state.setErrorData);
  const refreshFolders = useFolderStore((state) => state.refreshFolders);
  const flows = useFlowsManagerStore((state) => state.flows);

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
      | React.DragEvent<HTMLAnchorElement>,
    folderId: string,
  ) => {
    e.preventDefault();

    if (e.dataTransfer.types.some((types) => types === "Files")) {
      setFolderDragging(true);
    }
    setFolderIdDragging(folderId);
  };

  const dragEnter = (
    e:
      | React.DragEvent<HTMLDivElement>
      | React.DragEvent<HTMLButtonElement>
      | React.DragEvent<HTMLAnchorElement>,
    folderId: string,
  ) => {
    if (e.dataTransfer.types.some((types) => types === "Files")) {
      setFolderDragging(true);
    }
    setFolderIdDragging(folderId);
    e.preventDefault();
  };

  const dragLeave = (
    e:
      | React.DragEvent<HTMLDivElement>
      | React.DragEvent<HTMLButtonElement>
      | React.DragEvent<HTMLAnchorElement>,
  ) => {
    e.preventDefault();
    if (e.target === e.currentTarget) {
      setFolderDragging(false);
      setFolderIdDragging("");
    }
  };

  const onDrop = (
    e:
      | React.DragEvent<HTMLDivElement>
      | React.DragEvent<HTMLButtonElement>
      | React.DragEvent<HTMLAnchorElement>,
    folderId: string,
  ) => {
    if (e?.dataTransfer?.getData("flow")) {
      const data = JSON.parse(e?.dataTransfer?.getData("flow"));

      if (data) {
        uploadFromDragCard(data.id, folderId);
        return;
      }
    }

    e.preventDefault();
    handleFileDrop(e);
  };

  const uploadFromDragCard = (flowId, folderId) => {
    const selectedFlow = flows.find((flow) => flow.id === flowId);

    if (!selectedFlow) {
      throw new Error("Flow not found");
    }
    const updatedFlow = { ...selectedFlow, folder_id: folderId };

    const newName = addVersionToDuplicates(updatedFlow, flows);

    updatedFlow.name = newName;

    setFolderDragging(false);
    setFolderIdDragging("");

    updateFlowInDatabase(updatedFlow).then(() => {
      refreshFolders();
      triggerFolderChange(folderId);
    });
  };

  const uploadFormData = (data) => {
    const formData = new FormData();
    formData.append("file", data);
    setFolderDragging(false);
    setFolderIdDragging("");
    uploadFlowsFromFolders(formData).then(() => {
      refreshFolders();
      triggerFolderChange(folderId);
    });
  };

  return {
    dragOver,
    dragEnter,
    dragLeave,
    onDrop,
  };
};

export default useFileDrop;
