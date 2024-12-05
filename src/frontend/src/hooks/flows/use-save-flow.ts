import { useGetFlow } from "@/controllers/API/queries/flows/use-get-flow";
import { usePatchUpdateFlow } from "@/controllers/API/queries/flows/use-patch-update-flow";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useFlowStore from "@/stores/flowStore";
import { FlowType } from "@/types/flow";
import { customStringify } from "@/utils/reactflowUtils";
import { ReactFlowJsonObject } from "reactflow";

const useSaveFlow = () => {
  const flows = useFlowsManagerStore((state) => state.flows);
  const setFlows = useFlowsManagerStore((state) => state.setFlows);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const reactFlowInstance = useFlowStore((state) => state.reactFlowInstance);
  const nodes = useFlowStore((state) => state.nodes);
  const edges = useFlowStore((state) => state.edges);
  const setSaveLoading = useFlowsManagerStore((state) => state.setSaveLoading);
  const setCurrentFlow = useFlowStore((state) => state.setCurrentFlow);
  const currentSavedFlow = useFlowsManagerStore((state) => state.currentFlow);

  const { mutate: getFlow } = useGetFlow();
  const { mutate } = usePatchUpdateFlow();

  const currentFlow = useFlowStore((state) => state.currentFlow);
  const flowData = currentFlow?.data;

  const saveFlow = async (flow?: FlowType): Promise<void> => {
    if (
      customStringify(flow || currentFlow) !== customStringify(currentSavedFlow)
    ) {
      setSaveLoading(true);
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
                  flow!.data = flowResponse.data as ReactFlowJsonObject;
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
            mutate(
              {
                id,
                name,
                data: data!,
                description,
                folder_id,
                endpoint_name,
                locked,
              },
              {
                onSuccess: (updatedFlow) => {
                  setSaveLoading(false);
                  if (flows) {
                    // updates flow in state
                    setFlows(
                      flows.map((flow) => {
                        if (flow.id === updatedFlow.id) {
                          return updatedFlow;
                        }
                        return flow;
                      }),
                    );
                    setCurrentFlow(updatedFlow);
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
