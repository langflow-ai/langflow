import {
  UPLOAD_ALERT_LIST,
  WRONG_FILE_ERROR_ALERT,
} from "../../../constants/alerts_constants";
import { updateFlowInDatabase } from "../../../controllers/API";
import { uploadFlowsFromFolders } from "../../../pages/MainPage/services";
import useAlertStore from "../../../stores/alertStore";
import useFlowsManagerStore from "../../../stores/flowsManagerStore";
import { useFolderStore } from "../../../stores/foldersStore";
import { FlowType } from "../../../types/flow";

const useFileDrop = (folderId, folderChangeCallback) => {
  const setFolderDragging = useFolderStore((state) => state.setFolderDragging);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const getFoldersApi = useFolderStore((state) => state.getFoldersApi);
  const refreshFlows = useFlowsManagerStore((state) => state.refreshFlows);
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
      | React.DragEvent<HTMLAnchorElement>,
    folderId: string
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
    setFolderDragging(false);
  };

  const uploadFromDragCard = (flowId, folderId) => {
    const selectedFlow = flows.find((flow) => flow.id === flowId);

    if (!selectedFlow) {
      throw new Error("Flow not found");
    }

    const updatedFlow: FlowType = {
      ...selectedFlow,
      folder_id: folderId,
    };
    updateFlowInDatabase(updatedFlow).then(() => {
      getFoldersApi(true);
      triggerFolderChange(folderId);
    });
  };

  const uploadFormData = (data) => {
    const formData = new FormData();
    formData.append("file", data);

    uploadFlowsFromFolders(formData).then(() => {
      getFoldersApi(true);
      triggerFolderChange(folderId);
      refreshFlows();
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
