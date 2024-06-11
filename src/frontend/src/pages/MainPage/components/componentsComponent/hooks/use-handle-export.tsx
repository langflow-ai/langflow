import { useCallback } from "react";

const useExportFlows = (
  selectedFlowsComponentsCards,
  allFlows,
  downloadFlow,
  removeApiKeys,
  version,
  setSuccessData,
  setSelectedFlowsComponentsCards,
  handleSelectAll,
  cardTypes,
) => {
  const handleExport = useCallback(() => {
    selectedFlowsComponentsCards.forEach((selectedFlowId) => {
      const selectedFlow = allFlows.find((flow) => flow.id === selectedFlowId);
      if (selectedFlow) {
        downloadFlow(
          removeApiKeys({
            id: selectedFlow.id,
            data: selectedFlow.data,
            description: selectedFlow.description,
            name: selectedFlow.name,
            last_tested_version: version,
            is_component: false,
          }),
          selectedFlow.name,
          selectedFlow.description,
        );
      }
    });
    setSuccessData({ title: `${cardTypes} exported successfully` });
    setSelectedFlowsComponentsCards([]);
    handleSelectAll(false);
  }, [
    selectedFlowsComponentsCards,
    allFlows,
    downloadFlow,
    removeApiKeys,
    version,
    setSuccessData,
    setSelectedFlowsComponentsCards,
    handleSelectAll,
    cardTypes,
  ]);

  return { handleExport };
};

export default useExportFlows;
