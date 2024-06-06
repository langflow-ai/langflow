import { useFolderStore } from "../../../../../stores/foldersStore";

const useDeleteMultiple = (
  removeFlow,
  resetFilter,
  folderId,
  myCollectionId,
  setSuccessData,
  setErrorData,
) => {
  const handleDeleteMultiple = (selectedFlowsComponentsCards) => {
    const getFolderById = useFolderStore((state) => state.getFolderById);
    const getFoldersApi = useFolderStore((state) => state.getFoldersApi);

    removeFlow(selectedFlowsComponentsCards)
      .then(() => {
        resetFilter();
        getFoldersApi(true);
        if (!folderId || folderId === myCollectionId) {
          getFolderById(folderId ? folderId : myCollectionId);
        }
        setSuccessData({
          title: "Selected items deleted successfully",
        });
      })
      .catch(() => {
        setErrorData({
          title: "Error deleting items",
          list: ["Please try again"],
        });
      });
  };

  return { handleDeleteMultiple };
};

export default useDeleteMultiple;
