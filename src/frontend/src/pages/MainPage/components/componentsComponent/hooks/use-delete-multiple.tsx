import { useCallback } from "react";

const useDeleteMultipleFlows = (
  selectedFlowsComponentsCards,
  removeFlow,
  resetFilter,
  getFoldersApi,
  folderId,
  myCollectionId,
  getFolderById,
  setSuccessData,
  setErrorData,
) => {
  const handleDeleteMultiple = useCallback(() => {
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
  }, [
    selectedFlowsComponentsCards,
    removeFlow,
    resetFilter,
    getFoldersApi,
    folderId,
    myCollectionId,
    getFolderById,
    setSuccessData,
    setErrorData,
  ]);

  return { handleDeleteMultiple };
};

export default useDeleteMultipleFlows;
