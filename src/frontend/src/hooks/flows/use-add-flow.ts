import { UUID_PARSING_ERROR } from "@/constants/constants";
import { usePostAddFlow } from "@/controllers/API/queries/flows/use-post-add-flow";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useTypesStore } from "@/stores/typesStore";
import type { FlowType } from "@/types/flow";
import { extractApiErrorMessages } from "@/utils/apiError";
import {
  extractFieldsFromComponenents,
  processFlows,
} from "@/utils/reactflowUtils";
import useDeleteFlow from "./use-delete-flow";
import usePrepareFlows from "./use-prepare-flows";

const FLOW_CREATION_ERROR = "Flow creation error";
const FOLDER_NOT_FOUND_ERROR = "Folder not found. Redirecting to flows...";
const REDIRECT_DELAY = 3000;
const useAddFlow = () => {
  const navigate = useCustomNavigate();
  const flows = useFlowsManagerStore((state) => state.flows);
  const setFlows = useFlowsManagerStore((state) => state.setFlows);
  const { deleteFlow } = useDeleteFlow();

  const setNoticeData = useAlertStore.getState().setNoticeData;
  const { mutate: postAddFlow } = usePostAddFlow();
  const prepareFlows = usePrepareFlows();

  const addFlow = async (params?: {
    flow?: FlowType;
    override?: boolean;
    new_blank?: boolean;
  }): Promise<string> => {
    const flow = params?.flow;
    const [newFlow] = await prepareFlows([flow]);
    // Create a new flow with a default name if no flow is provided.
    if (params?.override && flow) {
      const flowId = flows?.find((f) => f.name === flow.name);
      if (flowId) {
        await deleteFlow({ id: flowId.id });
      }
    }

    return new Promise<string>((resolve, reject) => {
      postAddFlow(newFlow, {
        onSuccess: (createdFlow) => {
          // Add the new flow to the list of flows.
          const { data, flows: myFlows } = processFlows([
            createdFlow,
            ...(flows ?? []),
          ]);
          setFlows(myFlows);
          useTypesStore.setState((state) => ({
            data: { ...state.data, ["saved_components"]: data },
            ComponentFields: extractFieldsFromComponenents({
              ...state.data,
              ["saved_components"]: data,
            }),
          }));

          resolve(createdFlow.id);
        },
        onError: (error) => {
          const detail = error?.response?.data?.detail;
          if (Array.isArray(detail) && detail[0]?.type === UUID_PARSING_ERROR) {
            setNoticeData({
              title: FOLDER_NOT_FOUND_ERROR,
            });
            setTimeout(() => {
              navigate("/flows", { replace: true });
            }, REDIRECT_DELAY);

            reject(error);
            return;
          }

          useAlertStore.getState().setErrorData({
            title: FLOW_CREATION_ERROR,
            list: extractApiErrorMessages(error),
          });
          reject(error); // Re-throw the error so the caller can handle it if needed},
        },
      });
    });
  };

  return addFlow;
};

export default useAddFlow;
