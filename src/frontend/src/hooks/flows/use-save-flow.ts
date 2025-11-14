import type { ReactFlowJsonObject } from "@xyflow/react";
import { applyPatch } from "fast-json-patch";
import { useGetFlow } from "@/controllers/API/queries/flows/use-get-flow";
import type { PatchOperation } from "@/controllers/API/queries/flows/use-patch-json-patch-flow";
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
                    // Apply the patch operations to the current flow using fast-json-patch
                    // This efficiently handles nested updates like /data/1/template/field
                    const patchResult = applyPatch(
                      structuredClone(flow!),
                      patchResponse.operations,
                    );
                    const mergedFlow = {
                      ...patchResult.newDocument,
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
