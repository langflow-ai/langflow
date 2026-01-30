import { cloneDeep } from "lodash";
import { useParams } from "react-router-dom";
import { UUID_PARSING_ERROR } from "@/constants/constants";
import { usePostAddFlow } from "@/controllers/API/queries/flows/use-post-add-flow";
import { usePostFolders } from "@/controllers/API/queries/folders";
import useAlertStore from "@/stores/alertStore";
import useAuthStore from "@/stores/authStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useFolderStore } from "@/stores/foldersStore";
import { useGlobalVariablesStore } from "@/stores/globalVariablesStore/globalVariables";
import { useTypesStore } from "@/stores/typesStore";
import { useUtilityStore } from "@/stores/utilityStore";
import type { FlowType } from "@/types/flow";
import {
  addVersionToDuplicates,
  createNewFlow,
  extractFieldsFromComponenents,
  processDataFromFlow,
  processFlows,
  updateGroupRecursion,
} from "@/utils/reactflowUtils";
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
  const folders = useFolderStore((state) => state.folders);
  const setMyCollectionId = useFolderStore((state) => state.setMyCollectionId);

  const userData = useAuthStore((state) => state.userData);
  const hideGettingStartedProgress = useUtilityStore(
    (state) => state.hideGettingStartedProgress,
  );
  const isOnboarding =
    !hideGettingStartedProgress && !userData?.optins?.dialog_dismissed;

  const unavailableFields = useGlobalVariablesStore(
    (state) => state.unavailableFields,
  );
  const globalVariablesEntries = useGlobalVariablesStore(
    (state) => state.globalVariablesEntries,
  );

  const { mutate: postAddFlow } = usePostAddFlow();
  const { mutateAsync: postAddFolder } = usePostFolders();

  const addFlow = async (params?: {
    flow?: FlowType;
    override?: boolean;
    new_blank?: boolean;
  }): Promise<string> => {
    const flow = cloneDeep(params?.flow) ?? undefined;
    const flowData = flow
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

    // Determine folder_id, creating a new folder if needed
    let folder_id = folderId ?? myCollectionId ?? "";

    // If no folder exists, create one with the appropriate name based on onboarding state
    if (!folder_id && (!folders || folders.length === 0)) {
      try {
        const projectName = isOnboarding ? "Starter Project" : "New Project";
        const newFolder = await postAddFolder({
          data: {
            name: projectName,
            parent_id: null,
            description: "",
          },
        });
        folder_id = newFolder.id;
        setMyCollectionId(folder_id);
      } catch {
        // Continue with empty folder_id - backend will create default folder
      }
    }

    const flowsToCheckNames = flows?.filter(
      (f) => f.folder_id === myCollectionId,
    );
    const newFlow = createNewFlow(flowData!, folder_id, flow);
    const newName = addVersionToDuplicates(newFlow, flowsToCheckNames ?? []);
    newFlow.name = newName;
    newFlow.folder_id = folder_id;

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
