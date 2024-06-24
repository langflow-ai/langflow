import { useCallback } from "react";

const useDuplicateFlows = (
  selectedFlowsComponentsCards,
  addFlow,
  allFlows,
  resetFilter,
  getFoldersApi,
  folderId,
  myCollectionId,
  getFolderById,
  setSuccessData,
  setSelectedFlowsComponentsCards,
  handleSelectAll,
  cardTypes,
) => {
  const handleDuplicate = useCallback(() => {
    Promise.all(
      selectedFlowsComponentsCards.map((selectedFlow) =>
        addFlow(
          true,
          allFlows.find((flow) => flow.id === selectedFlow),
        ),
      ),
    ).then(() => {
      resetFilter();
      getFoldersApi(true);
      if (!folderId || folderId === myCollectionId) {
        getFolderById(folderId ? folderId : myCollectionId);
      }
      setSuccessData({ title: `${cardTypes} duplicated successfully` });
      setSelectedFlowsComponentsCards([]);
      handleSelectAll(false);
    });
  }, [
    selectedFlowsComponentsCards,
    addFlow,
    allFlows,
    resetFilter,
    getFoldersApi,
    folderId,
    myCollectionId,
    getFolderById,
    setSuccessData,
    setSelectedFlowsComponentsCards,
    handleSelectAll,
    cardTypes,
  ]);

  return { handleDuplicate };
};

export default useDuplicateFlows;
