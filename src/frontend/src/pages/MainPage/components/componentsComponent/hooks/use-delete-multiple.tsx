import { FolderType } from "@/pages/MainPage/entities";
import { FlowType } from "@/types/flow";
import { useCallback } from "react";

const useDeleteMultipleFlows = (
  selectedFlowsComponentsCards: string[],
  removeFlow: (selectedFlowsComponentsCards: string[]) => Promise<void>,
  resetFilter: () => void,
  getFoldersApi: (refetch?: boolean) => Promise<void>,
  folderId: string | undefined,
  myCollectionId: string,
  getFolderById: (id: string) => void,
  setSuccessData: (data: { title: string }) => void,
  setErrorData: (data: { title: string; list: string[] }) => void,
  setAllFlows: (flows: FlowType[]) => void,
  setSelectedFolder: (folder: FolderType | null) => void,
) => {
  const handleDeleteMultiple = useCallback(() => {
    removeFlow(selectedFlowsComponentsCards)
      .then(() => {
        setAllFlows([]);
        setSelectedFolder(null);

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
