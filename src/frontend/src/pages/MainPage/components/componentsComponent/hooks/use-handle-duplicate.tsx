import { useCallback } from "react";
import { XYPosition } from "reactflow";
import { FlowType } from "../../../../../types/flow";

const useDuplicateFlows = (
  selectedFlowsComponentsCards: string[],
  addFlow: (
    newProject: boolean,
    flow?: FlowType,
    override?: boolean,
    position?: XYPosition,
    fromDragAndDrop?: boolean,
  ) => Promise<string | undefined>,
  allFlows: any[],
  resetFilter: () => void,
  getFoldersApi: (
    refetch?: boolean,
    startupApplication?: boolean,
  ) => Promise<void>,
  folderId: string,
  myCollectionId: string,
  getFolderById: (id: string) => void,
  setSuccessData: (data: { title: string }) => void,
  setSelectedFlowsComponentsCards: (
    selectedFlowsComponentsCards: string[],
  ) => void,
  handleSelectAll: (select: boolean) => void,
  cardTypes: string,
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
