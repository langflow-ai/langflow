import { FolderType } from "../../../pages/MainPage/entities";
import { addFolder, updateFolder } from "../../../pages/MainPage/services";
import useAlertStore from "../../../stores/alertStore";
import { useFolderStore } from "../../../stores/foldersStore";

const useFolderSubmit = (
  setOpen: (a: boolean) => void,
  folderToEdit: FolderType | null,
) => {
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const getFoldersApi = useFolderStore((state) => state.getFoldersApi);

  const onSubmit = (data) => {
    if (folderToEdit) {
      updateFolder(data, folderToEdit?.id!).then(
        () => {
          setSuccessData({
            title: "Folder updated successfully.",
          });
          getFoldersApi(true);
          setOpen(false);
        },
        (reason) => {
          if (reason) {
            setErrorData({
              title: `Error updating folder.`,
            });
            console.error(reason);
          } else {
            getFoldersApi(true);
            setOpen(false);
          }
        },
      );
    } else {
      addFolder(data).then(
        () => {
          setSuccessData({
            title: "Folder created successfully.",
          });
          getFoldersApi(true);
          setOpen(false);
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
