import type { ReactFlowJsonObject } from "@xyflow/react";
import type { Operation as JsonPatchOperation } from "fast-json-patch";
import { useGetFlow } from "@/controllers/API/queries/flows/use-get-flow";
import { usePatchJsonPatchFlow } from "@/controllers/API/queries/flows/use-patch-json-patch-flow";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { AllNodeType, EdgeType, FlowType } from "@/types/flow";
import { compareFlows } from "@/utils/flowPatchUtils";
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

          const { id } = flow;
          if (
            !currentSavedFlow?.data?.nodes.length ||
            flow.data!.nodes.length > 0
          ) {
            // Use jsondiffpatch with ID-aware array diffing
            // This generates ~2 operations for node removal vs ~225 with index-based diffing
            const operations = compareFlows(
              currentSavedFlow || {},
              flow,
            ) as JsonPatchOperation[];

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
                    // The local flow already has the user's changes applied.
                    // We only need to merge server-controlled fields (id, updated_at).
                    // Re-applying the same operations would corrupt array data
                    // (e.g., removing wrong node when indices shift).
                    const mergedFlow = {
                      ...structuredClone(flow!),
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
