import { useLocation } from "react-router-dom";
import {
  CONSOLE_ERROR_MSG,
  UPLOAD_ALERT_LIST,
  WRONG_FILE_ERROR_ALERT,
} from "../../../constants/alerts_constants";
import useAlertStore from "../../../stores/alertStore";
import { useFolderStore } from "../../../stores/foldersStore";

const useFileDrop = (uploadFlow, type) => {
  const location = useLocation();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const getFolderById = useFolderStore((state) => state.getFolderById);
  const folderId = location?.state?.folderId;
  const myCollectionId = useFolderStore((state) => state.myCollectionId);

  const handleFileDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.types.some((type) => type === "Files")) {
      const file = e.dataTransfer.files.item(0);

      if (file.type === "application/json") {
        const reader = new FileReader();

        reader.onload = (event) => {
          const fileContent = event.target!.result;
          const fileContentJson = JSON.parse(fileContent as string);
          const is_component = fileContentJson.is_component;
          uploadFlow({
            newProject: true,
            file: file,
            isComponent: type === "all" ? null : type === "component",
          })
            .then(() => {
              setSuccessData({
                title: `${
                  is_component ? "Component" : "Flow"
                } uploaded successfully`,
              });
              getFolderById(folderId ? folderId : myCollectionId);
            })
            .catch((error) => {
              setErrorData({
                title: CONSOLE_ERROR_MSG,
                list: [error],
              });
            });
        };

        reader.readAsText(file);
      } else {
        setErrorData({
          title: WRONG_FILE_ERROR_ALERT,
          list: [UPLOAD_ALERT_LIST],
        });
      }
    }
  };

  return [handleFileDrop];
};

export default useFileDrop;
