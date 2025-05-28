import { UUID_PARSING_ERROR } from "@/constants/constants";
import { usePostAddFlow } from "@/controllers/API/queries/flows/use-post-add-flow";
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
import { cloneDeep } from "lodash";
import { useParams } from "react-router-dom";
import useDeleteFlow from "./use-delete-flow";

const FLOW_CREATION_ERROR = "Flow creation error";
const FOLDER_NOT_FOUND_ERROR = "Folder not found. Redirecting to flows...";
const FLOW_CREATION_ERROR_MESSAGE =
  "An unexpected error occurred, please try again";
const REDIRECT_DELAY = 3000;
const useAddFlow = () => {
  const flows = useFlowsManagerStore((state) => state.flows);
  const setFlows = useFlowsManagerStore((state) => state.setFlows);
  const { deleteFlow } = useDeleteFlow();

  const setNoticeData = useAlertStore.getState().setNoticeData;
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);

  const unavailableFields = useGlobalVariablesStore(
    (state) => state.unavailableFields,
  );
  const globalVariablesEntries = useGlobalVariablesStore(
    (state) => state.globalVariablesEntries,
  );

  const { mutate: postAddFlow } = usePostAddFlow();

  const addFlow = async (params?: {
    flow?: FlowType;
    override?: boolean;
    new_blank?: boolean;
  }) => {
    return new Promise(async (resolve, reject) => {
      const flow = cloneDeep(params?.flow) ?? undefined;
      let flowData = flow
        ? await processDataFromFlow(flow)
        : { nodes: [], edges: [], viewport: { zoom: 1, x: 0, y: 0 } };
      flowData?.nodes.forEach((node) => {
        updateGroupRecursion(
          node,
          flowData?.edges,
          unavailableFields,
          globalVariablesEntries,
        );
      });
      // Create a new flow with a default name if no flow is provided.
      if (params?.override && flow) {
        const flowId = flows?.find((f) => f.name === flow.name);
        if (flowId) {
          await deleteFlow({ id: flowId.id });
        }
      }

      const folder_id = folderId ?? myCollectionId ?? "";
      const flowsToCheckNames = flows?.filter(
        (f) => f.folder_id === myCollectionId,
      );
      const newFlow = createNewFlow(flowData!, folder_id, flow);
      const newName = addVersionToDuplicates(newFlow, flowsToCheckNames ?? []);
      newFlow.name = newName;
      newFlow.folder_id = folder_id;

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
          if (error?.response?.data?.detail[0]?.type === UUID_PARSING_ERROR) {
            setNoticeData({
              title: FOLDER_NOT_FOUND_ERROR,
            });
            setTimeout(() => {
              window.location.href = `/flows`;
            }, REDIRECT_DELAY);

            return;
          }

          if (error.response?.data?.detail) {
            useAlertStore.getState().setErrorData({
              title: FLOW_CREATION_ERROR,
              list: [error.response?.data?.detail],
            });
          } else {
            useAlertStore.getState().setErrorData({
              title: FLOW_CREATION_ERROR,
              list: [error.message ?? FLOW_CREATION_ERROR_MESSAGE],
            });
          }
          reject(error); // Re-throw the error so the caller can handle it if needed},
        },
      });
    });
  };

  return addFlow;
};

export default useAddFlow;
