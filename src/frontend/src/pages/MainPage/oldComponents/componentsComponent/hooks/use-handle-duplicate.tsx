import { useGetRefreshFlows } from "@/controllers/API/queries/flows/use-get-refresh-flows";
import { usePostAddFlow } from "@/controllers/API/queries/flows/use-post-add-flow";
import useAddFlow from "@/hooks/flows/use-add-flow";
import { useFolderStore } from "@/stores/foldersStore";
import { useTypesStore } from "@/stores/typesStore";
import {
  addVersionToDuplicates,
  createNewFlow,
  extractFieldsFromComponenents,
  processFlows,
} from "@/utils/reactflowUtils";
import { toTitleCase } from "@/utils/utils";
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
  const { mutate: postAddFlow } = usePostAddFlow();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);

  const { mutate: refreshFlows } = useGetRefreshFlows();

  const flowsToCheckNames = allFlows?.filter(
    (f) => f.folder_id === myCollectionId,
  );

  const handleDuplicate = useCallback(async () => {
    try {
      const createdFlows = await Promise.all(
        selectedFlowsComponentsCards.map((selectedFlow) => {
          const flow = allFlows.find((flow) => flow.id === selectedFlow);
          const folder_id = flow?.folder_id ?? myCollectionId ?? "";

          const newFlow = createNewFlow(flow?.data!, folder_id, flow);

          const newName = addVersionToDuplicates(
            newFlow,
            flowsToCheckNames ?? [],
          );
          newFlow.name = newName;
          newFlow.folder_id = folder_id;

          postAddFlow(newFlow, {
            onSuccess: (createdFlow) => {
              // Add the new flow to the list of flows.
              const { data, flows: myFlows } = processFlows([
                createdFlow,
                ...(flowsToCheckNames ?? []),
              ]);
              useTypesStore.setState((state) => ({
                data: { ...state.data, ["saved_components"]: data },
                ComponentFields: extractFieldsFromComponenents({
                  ...state.data,
                  ["saved_components"]: data,
                }),
              }));

              refreshFlows({
                get_all: true,
                header_flows: true,
              });
            },
          });
          resetFilter();
          setSuccessData({
            title: `${toTitleCase(cardTypes)} duplicated successfully`,
          });
          setSelectedFlowsComponentsCards([]);
          handleSelectAll(false);
          return createdFlows;
        }),
      );
    } catch (error) {
      console.error("Failed to duplicate flows:", error);
    }
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
