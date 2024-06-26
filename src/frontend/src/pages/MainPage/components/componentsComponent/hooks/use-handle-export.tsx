import { useCallback } from "react";
import { FlowType } from "../../../../../types/flow";

const useExportFlows = (
  selectedFlowsComponentsCards: string[],
  allFlows: Array<FlowType>,
  downloadFlow: (flow: any, name: string, description: string) => void,
  removeApiKeys: (flow: any) => any,
  version: string,
  setSuccessData: (data: { title: string }) => void,
  setSelectedFlowsComponentsCards: (
    selectedFlowsComponentsCards: string[],
  ) => void,
  handleSelectAll: (select: boolean) => void,
  cardTypes: string,
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
            endpoint_name: selectedFlow.endpoint_name,
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
