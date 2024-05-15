import useAlertStore from "../../../stores/alertStore";
import { useFolderStore } from "../../../stores/foldersStore";
import { deleteFolder } from "../services";

const useDeleteFolder = ({ navigate, getFoldersApi }) => {
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const folderToEdit = useFolderStore((state) => state.folderToEdit);

  const handleDeleteFolder = () => {
    deleteFolder(folderToEdit?.id!)
      .then(() => {
        setSuccessData({
          title: "Folder deleted successfully.",
        });
        getFoldersApi(true);
        navigate("/flows");
      })
      .catch(() => {
        setErrorData({
          title: "Error deleting folder.",
        });
      });
  };

  return { handleDeleteFolder };
};

export default useDeleteFolder;
