import { usePostUploadFlowToFolder } from "@/controllers/API/queries/folders/use-post-upload-to-folder";
import useSaveFlow from "@/hooks/flows/use-save-flow";
import {
  UPLOAD_ALERT_LIST,
  WRONG_FILE_ERROR_ALERT,
} from "../../../../constants/alerts_constants";
import useAlertStore from "../../../../stores/alertStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { useFolderStore } from "../../../../stores/foldersStore";
import { addVersionToDuplicates } from "../../../../utils/reactflowUtils";

const useFileDrop = (folderId: string) => {
  const setFolderDragging = useFolderStore((state) => state.setFolderDragging);
  const setFolderIdDragging = useFolderStore(
    (state) => state.setFolderIdDragging,
  );

  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const saveFlow = useSaveFlow();
  const flows = useFlowsManagerStore((state) => state.flows);

  const { mutate: uploadFlowToFolder } = usePostUploadFlowToFolder();
  const handleFileDrop = async (e, folderId) => {
    if (e.dataTransfer.types.some((type) => type === "Files")) {
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        const firstFile = e.dataTransfer.files[0];
        if (firstFile.type === "application/json") {
          uploadFormData(firstFile, folderId);
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
    handleFileDrop(e, folderId);
  };

  const uploadFromDragCard = (flowId, folderId) => {
    const selectedFlow = flows?.find((flow) => flow.id === flowId);

    if (!selectedFlow) {
      throw new Error("Flow not found");
    }
    const updatedFlow = { ...selectedFlow, folder_id: folderId };

    const flowsToCheckNames = flows?.filter(
      (f) => f.folder_id === myCollectionId,
    );

    const newName = addVersionToDuplicates(
      updatedFlow,
      flowsToCheckNames ?? [],
    );

    updatedFlow.name = newName;

    setFolderDragging(false);
    setFolderIdDragging("");

    saveFlow(updatedFlow);
  };

  const uploadFormData = (data, folderId) => {
    const formData = new FormData();
    formData.append("file", data);
    setFolderDragging(false);
    setFolderIdDragging("");

    uploadFlowToFolder({ flows: formData, folderId });
  };

  return {
    dragOver,
    dragEnter,
    dragLeave,
    onDrop,
  };
};

export default useFileDrop;
