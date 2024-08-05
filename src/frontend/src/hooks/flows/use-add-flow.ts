import { usePostSaveFlow } from "@/controllers/API/queries/flows/use-post-save-flow";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useFolderStore } from "@/stores/foldersStore";
import { useGlobalVariablesStore } from "@/stores/globalVariablesStore/globalVariables";
import { useTypesStore } from "@/stores/typesStore";
import { FlowType } from "@/types/flow";
import {
  addVersionToDuplicates,
  createNewFlow,
  extractFieldsFromComponenents,
  processDataFromFlow,
  processFlows,
  updateGroupRecursion,
} from "@/utils/reactflowUtils";

const useAddFlow = () => {
  const unavaliableFields = useGlobalVariablesStore(
    (state) => state.unavailableFields,
  );
  const globalVariablesEntries = useGlobalVariablesStore(
    (state) => state.globalVariablesEntries,
  );
  const flows = useFlowsManagerStore((state) => state.flows);
  const setFlows = useFlowsManagerStore((state) => state.setFlows);
  const deleteComponent = useFlowsManagerStore(
    (state) => state.deleteComponent,
  );
  const setIsLoading = useFlowsManagerStore((state) => state.setIsLoading);

  const { mutate: saveFlow } = usePostSaveFlow();

  const addFlow = async ({
    flow,
    override,
  }: {
    flow?: FlowType;
    override?: boolean;
  }) => {
    return new Promise(async (resolve, reject) => {
      let flowData = flow
        ? processDataFromFlow(flow)
        : { nodes: [], edges: [], viewport: { zoom: 1, x: 0, y: 0 } };
      flowData?.nodes.forEach((node) => {
        updateGroupRecursion(
          node,
          flowData?.edges,
          unavaliableFields,
          globalVariablesEntries,
        );
      });
      // Create a new flow with a default name if no flow is provided.
      const folder_id = useFolderStore.getState().folderUrl;
      const my_collection_id = useFolderStore.getState().myCollectionId;

      if (override) {
        await deleteComponent(flow!.name);
      }
      const newFlow = createNewFlow(
        flowData!,
        flow!,
        folder_id || my_collection_id!,
      );

      const newName = addVersionToDuplicates(newFlow, flows);
      newFlow.name = newName;
      newFlow.folder_id = useFolderStore.getState().folderUrl;

      saveFlow(newFlow, {
        onSuccess: ({ id }) => {
          newFlow.id = id;
          // Add the new flow to the list of flows.
          const { data, flows: myFlows } = processFlows([newFlow, ...flows]);
          setFlows(myFlows);
          useTypesStore.setState((state) => ({
            data: { ...state.data, ["saved_components"]: data },
            ComponentFields: extractFieldsFromComponenents({
              ...state.data,
              ["saved_components"]: data,
            }),
          }));
          setIsLoading(false);
          resolve(id);
        },
        onError: (error) => {
          if (error.response?.data?.detail) {
            useAlertStore.getState().setErrorData({
              title: "Could not load flows from database",
              list: [error.response?.data?.detail],
            });
          } else {
            useAlertStore.getState().setErrorData({
              title: "Could not load flows from database",
              list: [
                error.message ??
                  "An unexpected error occurred, please try again",
              ],
            });
          }
          setIsLoading(false);
          reject(error); // Re-throw the error so the caller can handle it if needed},
        },
      });
    });
  };

  return addFlow;
};

export default useAddFlow;
