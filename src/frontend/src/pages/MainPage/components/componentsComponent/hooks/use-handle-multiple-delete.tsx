const useDeleteMultiple = (
  removeFlow,
  resetFilter,
  getFoldersApi,
  getFolderById,
  folderId,
  myCollectionId,
  setSuccessData,
  setErrorData
) => {
  const handleDeleteMultiple = (selectedFlowsComponentsCards) => {
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
