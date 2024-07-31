import { useLocation } from "react-router-dom";
import { XYPosition } from "reactflow";
import {
  CONSOLE_ERROR_MSG,
  UPLOAD_ALERT_LIST,
  WRONG_FILE_ERROR_ALERT,
} from "../../../constants/alerts_constants";
import useAlertStore from "../../../stores/alertStore";
import { useFolderStore } from "../../../stores/foldersStore";

const useFileDrop = (
  uploadFlow: ({
    newProject,
    file,
    isComponent,
    position,
  }: {
    newProject: boolean;
    file?: File;
    isComponent: boolean | null;
    position?: XYPosition;
  }) => Promise<string | never>,
  type,
) => {
  const location = useLocation();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const getFolderById = useFolderStore((state) => state.getFolderById);
  const folderId = location?.state?.folderId;
  const myCollectionId = useFolderStore((state) => state.myCollectionId);

  const handleFileDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.types.some((type) => type === "Files")) {
      const files: FileList = e.dataTransfer.files;

      const uploadPromises: Promise<any>[] = [];

      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        if (file.type === "application/json") {
          const reader = new FileReader();
          const FileReaderPromise: Promise<void> = new Promise(
            (resolve, reject) => {
              reader.onload = (event) => {
                const fileContent = event.target!.result;
                const fileContentJson = JSON.parse(fileContent as string);
                const is_component = fileContentJson.is_component;
                uploadFlow({
                  newProject: true,
                  file: file,
                  isComponent: type === "all" ? null : type === "component",
                })
                  .then((_) => resolve())
                  .catch((error) => {
                    reject(error);
                  });
              };
              reader.readAsText(file);
            },
          );
          uploadPromises.push(FileReaderPromise);
        }
      }

      Promise.all(uploadPromises)
        .then(() => {
          setSuccessData({
            title: `All files uploaded successfully`,
          });
          getFolderById(folderId ? folderId : myCollectionId);
        })
        .catch((error) => {
          setErrorData({
            title: CONSOLE_ERROR_MSG,
            list: [error],
          });
        });
    }
  };
  return [handleFileDrop];
};

export default useFileDrop;
