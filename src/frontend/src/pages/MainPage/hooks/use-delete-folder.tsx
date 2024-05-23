import useAlertStore from "../../../stores/alertStore";
import { useFolderStore } from "../../../stores/foldersStore";
import { deleteFolder, getFolderById } from "../services";

const useDeleteFolder = ({ navigate, getFoldersApi }) => {
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const folderToEdit = useFolderStore((state) => state.folderToEdit);
  const myCollectionId = useFolderStore((state) => state.myCollectionId);

  const handleDeleteFolder = () => {
    deleteFolder(folderToEdit?.id!)
      .then(() => {
        setSuccessData({
          title: "Folder deleted successfully.",
        });
        getFolderById(myCollectionId!);
        getFoldersApi(true);
        navigate("/all");
      })
      .catch((err) => {
        console.error(err);
        setErrorData({
          title: "Error deleting folder.",
        });
      });
  };

  return { handleDeleteFolder };
};

export default useDeleteFolder;
