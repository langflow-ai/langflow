const useExportFlows = (
  selectedFlowsComponentsCards,
  allFlows,
  downloadFlow,
  removeApiKeys,
  version,
  setSuccessData
) => {
  const handleExport = () => {
    selectedFlowsComponentsCards.forEach((selectedFlowId) => {
      const selectedFlow = allFlows.find((flow) => flow.id === selectedFlowId);
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
        selectedFlow.description
      );
    });
    setSuccessData({ title: "Flows exported successfully" });
  };

  return { handleExport };
};

export default useExportFlows;
