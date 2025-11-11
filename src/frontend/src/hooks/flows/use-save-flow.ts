import type { ReactFlowJsonObject } from "@xyflow/react";
import { compare } from "fast-json-patch";
import { useGetFlow } from "@/controllers/API/queries/flows/use-get-flow";
import type { PatchOperation } from "@/controllers/API/queries/flows/use-patch-json-patch-flow";
import { usePatchJsonPatchFlow } from "@/controllers/API/queries/flows/use-patch-json-patch-flow";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { AllNodeType, EdgeType, FlowType } from "@/types/flow";
import { customStringify } from "@/utils/reactflowUtils";

const useSaveFlow = () => {
  const setFlows = useFlowsManagerStore((state) => state.setFlows);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSaveLoading = useFlowsManagerStore((state) => state.setSaveLoading);
  const setCurrentFlow = useFlowStore((state) => state.setCurrentFlow);

  const { mutate: getFlow } = useGetFlow();
  const { mutate } = usePatchJsonPatchFlow();

  const saveFlow = async (flow?: FlowType): Promise<void> => {
    const currentFlow = useFlowStore.getState().currentFlow;
    const currentSavedFlow = useFlowsManagerStore.getState().currentFlow;
    if (
      customStringify(flow || currentFlow) !== customStringify(currentSavedFlow)
    ) {
      setSaveLoading(true);

      const flowData = currentFlow?.data;
      const nodes = useFlowStore.getState().nodes;
      const edges = useFlowStore.getState().edges;
      const reactFlowInstance = useFlowStore.getState().reactFlowInstance;

      return new Promise<void>((resolve, reject) => {
        if (currentFlow) {
          flow = flow || {
            ...currentFlow,
            data: {
              ...flowData,
              nodes,
              edges,
              viewport: reactFlowInstance?.getViewport() ?? {
                zoom: 1,
                x: 0,
                y: 0,
              },
            },
          };
        }

        if (flow) {
          if (!flow?.data) {
            getFlow(
              { id: flow!.id },
              {
                onSuccess: (flowResponse) => {
                  flow!.data = flowResponse.data as ReactFlowJsonObject<
                    AllNodeType,
                    EdgeType
                  >;
                },
              },
            );
          }

          const {
            id,
            name,
            data,
            description,
            folder_id,
            endpoint_name,
            locked,
          } = flow;
          if (!currentSavedFlow?.data?.nodes.length || data!.nodes.length > 0) {
            // Use fast-json-patch to automatically detect changes
            // This is more efficient than manually building operations
            const operations = compare(
              currentSavedFlow || {},
              flow,
            ) as PatchOperation[];

            mutate(
              {
                id,
                operations,
              },
              {
                onSuccess: (patchResponse) => {
                  const flows = useFlowsManagerStore.getState().flows;
                  setSaveLoading(false);
                  if (flows) {
                    // Merge the patched data into the current flow
                    const mergedFlow = {
                      ...flow!,
                      ...patchResponse.patched_data,
                      id: patchResponse.id,
                      updated_at: patchResponse.updated_at,
                    };

                    // updates flow in state
                    setFlows(
                      flows.map((f) => {
                        if (f.id === patchResponse.id) {
                          return mergedFlow;
                        }
                        return f;
                      }),
                    );
                    setCurrentFlow(mergedFlow);
                    resolve();
                  } else {
                    setErrorData({
                      title: "Failed to save flow",
                      list: ["Flows variable undefined"],
                    });
                    reject(new Error("Flows variable undefined"));
                  }
                },
                onError: (e) => {
                  setErrorData({
                    title: "Failed to save flow",
                    list: [e.message],
                  });
                  setSaveLoading(false);
                  reject(e);
                },
              },
            );
          } else {
            setSaveLoading(false);
          }
        } else {
          setErrorData({
            title: "Failed to save flow",
            list: ["Flow not found"],
          });
          reject(new Error("Flow not found"));
        }
      });
    }
  };

  return saveFlow;
};

export default useSaveFlow;
