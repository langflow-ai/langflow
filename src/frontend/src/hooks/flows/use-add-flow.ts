import { BROKEN_EDGES_WARNING } from "@/constants/constants";
import { usePostSaveFlow } from "@/controllers/API/queries/flows/use-post-save-flow";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useFlowStore from "@/stores/flowStore";
import { useFolderStore } from "@/stores/foldersStore";
import { useGlobalVariablesStore } from "@/stores/globalVariablesStore/globalVariables";
import { useTypesStore } from "@/stores/typesStore";
import { FlowType } from "@/types/flow";
import {
  addVersionToDuplicates,
  createNewFlow,
  detectBrokenEdgesEdges,
  extractFieldsFromComponenents,
  processDataFromFlow,
  processFlows,
  updateGroupRecursion,
} from "@/utils/reactflowUtils";
import { brokenEdgeMessage } from "@/utils/utils";
import { XYPosition } from "reactflow";

const useAddFlow = () => {
  const unavaliableFields = useGlobalVariablesStore(
    (state) => state.unavaliableFields,
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
    newProject = true,
    flow,
    override,
    position,
  }: {
    newProject?: Boolean;
    flow?: FlowType;
    override?: boolean;
    position?: XYPosition;
  }) => {
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
    if (newProject) {
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

      return new Promise((resolve, reject) =>
        saveFlow(newFlow, {
          onSuccess: ({ id }) => {
            newFlow.id = id;
            // Add the new flow to the list of flows.
            const { data, flows: myFlows } = processFlows([newFlow, ...flows]);
            setFlows(myFlows);
            setIsLoading(false);
            useTypesStore.setState((state) => ({
              data: { ...state.data, ["saved_components"]: data },
              ComponentFields: extractFieldsFromComponenents({
                ...state.data,
                ["saved_components"]: data,
              }),
            }));
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
            reject(error); // Re-throw the error so the caller can handle it if needed},
          },
        }),
      );
    } else {
      let brokenEdges = detectBrokenEdgesEdges(
        flow!.data!.nodes,
        flow!.data!.edges,
      );
      if (brokenEdges.length > 0) {
        useAlertStore.getState().setErrorData({
          title: BROKEN_EDGES_WARNING,
          list: brokenEdges.map((edge) => brokenEdgeMessage(edge)),
        });
      }
      useFlowStore
        .getState()
        .paste(
          { nodes: flow!.data!.nodes, edges: flow!.data!.edges },
          position ?? { x: 10, y: 10 },
        );
    }
  };

  return addFlow;
};

export default useAddFlow;
