import { SAVE_DEBOUNCE_TIME } from "@/constants/constants";
import { usePatchUpdateFlow } from "@/controllers/API/queries/flows/use-patch-update-flow";
import useAlertStore from "@/stores/alertStore";
import useAuthStore from "@/stores/authStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { FlowType } from "@/types/flow";
import { debounce } from "lodash";

const useSaveFlow = () => {
  const flows = useFlowsManagerStore((state) => state.flows);
  const setFlows = useFlowsManagerStore((state) => state.setFlows);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const user = useAuthStore((state) => state.userData);

  const shouldAutosave = Boolean(process.env.LANGFLOW_AUTO_SAVE) ?? true;

  const { mutate } = usePatchUpdateFlow();

  const autoSaveFlow = shouldAutosave
    ? debounce((flow?: FlowType) => {
        saveFlow(flow);
      }, SAVE_DEBOUNCE_TIME)
    : () => {};

  const saveFlow = async (flow?: FlowType): Promise<void> => {
    return new Promise<void>((resolve, reject) => {
      flow = flow || flows.find((flow) => flow.id === currentFlowId);
      if (flow && flow.data) {
        const { id, name, data, description, folder_id, endpoint_name } = flow;
        mutate(
          { id, name, data, description, folder_id, endpoint_name },
          {
            onSuccess: (updatedFlow) => {
              if (updatedFlow) {
                // updates flow in state
                setFlows(
                  flows.map((flow) => {
                    if (flow.id === updatedFlow.id) {
                      return updatedFlow;
                    }
                    return flow;
                  }),
                );
                resolve();
              }
            },
            onError: (e) => {
              setErrorData({
                title: "Failed to save flow",
                list: [e.message],
              });
              reject(e);
            },
          },
        );
      } else {
        reject(new Error("Flow not found"));
      }
    });
  };

  return { saveFlow, autoSaveFlow };
};

export default useSaveFlow;
