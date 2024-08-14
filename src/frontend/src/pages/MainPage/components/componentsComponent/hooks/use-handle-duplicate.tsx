import useAddFlow from "@/hooks/flows/use-add-flow";
import { useCallback } from "react";

const useDuplicateFlows = (
  selectedFlowsComponentsCards: string[],
  allFlows: any[],
  resetFilter: () => void,
  setSuccessData: (data: { title: string }) => void,
  setSelectedFlowsComponentsCards: (
    selectedFlowsComponentsCards: string[],
  ) => void,
  handleSelectAll: (select: boolean) => void,
  cardTypes: string,
) => {
  const addFlow = useAddFlow();
  const handleDuplicate = useCallback(() => {
    Promise.all(
      selectedFlowsComponentsCards.map((selectedFlow) =>
        addFlow({ flow: allFlows.find((flow) => flow.id === selectedFlow) }),
      ),
    ).then(() => {
      resetFilter();
      setSuccessData({ title: `${cardTypes} duplicated successfully` });
      setSelectedFlowsComponentsCards([]);
      handleSelectAll(false);
    });
  }, [
    selectedFlowsComponentsCards,
    addFlow,
    allFlows,
    resetFilter,
    setSuccessData,
    setSelectedFlowsComponentsCards,
    handleSelectAll,
    cardTypes,
  ]);

  return { handleDuplicate };
};

export default useDuplicateFlows;
