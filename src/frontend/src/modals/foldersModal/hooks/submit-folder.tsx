import { useNavigate } from "react-router-dom";
import { addFolder, updateFolder } from "../../../pages/MainPage/services";
import useAlertStore from "../../../stores/alertStore";
import { useFolderStore } from "../../../stores/foldersStore";

const useFolderSubmit = (setOpen, folderToEdit) => {
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const getFoldersApi = useFolderStore((state) => state.getFoldersApi);
  const navigate = useNavigate();

  const onSubmit = (data) => {
    if (folderToEdit) {
      updateFolder(data, folderToEdit?.id!).then(
        () => {
          setSuccessData({
            title: "Folder updated successfully.",
          });
          getFoldersApi(true);
          setOpen(false);
          navigate(`flows/folder/${folderToEdit.id}`, {
            state: { folderId: folderToEdit.id },
          });
        },
        () => {
          setErrorData({
            title: `Error updating folder.`,
          });
        },
      );
    } else {
      addFolder(data).then(
        (res) => {
          setSuccessData({
            title: "Folder created successfully.",
          });
          getFoldersApi(true);
          setOpen(false);
          navigate(`flows/folder/${res.id}`, { state: { folderId: res.id } });
        },
        () => {
          setErrorData({
            title: `Error creating folder.`,
          });
        },
      );
    }
  };

  return { onSubmit, open, setOpen };
};

export default useFolderSubmit;
