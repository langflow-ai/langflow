import { useQueryClient } from "@tanstack/react-query";
import { cloneDeep } from "lodash";
import { useParams } from "react-router-dom";
import { getGlobalVariablesQueryKey } from "@/controllers/API/helpers/global-variable-scope";
import { getSettledSuccessfulQueryData } from "@/controllers/API/helpers/query-cache";
import { usePostFolders } from "@/controllers/API/queries/folders";
import { fetchGlobalVariables } from "@/controllers/API/queries/variables/use-get-global-variables";
import useAuthStore from "@/stores/authStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useFolderStore } from "@/stores/foldersStore";
import getUnavailableFields from "@/stores/globalVariablesStore/utils/get-unavailable-fields";
import { useUtilityStore } from "@/stores/utilityStore";
import type { FlowType } from "@/types/flow";
import type { GlobalVariable } from "@/types/global_variables";
import { getFolderScopedDuplicateName } from "@/utils/flow-naming";
import {
  createNewFlow,
  processDataFromFlow,
  updateGroupRecursion,
} from "@/utils/reactflowUtils";
import { withNodesTableRowIds } from "@/utils/table-row-ids";

const usePrepareFlows = () => {
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const folders = useFolderStore((state) => state.folders);
  const setMyCollectionId = useFolderStore((state) => state.setMyCollectionId);
  const flows = useFlowsManagerStore((state) => state.flows);
  const userData = useAuthStore((state) => state.userData);
  const hideGettingStartedProgress = useUtilityStore(
    (state) => state.hideGettingStartedProgress,
  );
  const isOnboarding =
    !hideGettingStartedProgress && !userData?.optins?.dialog_dismissed;
  const queryClient = useQueryClient();
  const { mutateAsync: postAddFolder } = usePostFolders();

  return async (sourceFlows: (FlowType | undefined)[]) => {
    const normalized = await Promise.all(
      sourceFlows.map(async (sourceFlow) => {
        const flow = cloneDeep(sourceFlow);
        const flowData = flow
          ? await processDataFromFlow(flow)
          : { nodes: [], edges: [], viewport: { zoom: 1, x: 0, y: 0 } };
        return { flow, flowData };
      }),
    );

    let folder_id = folderId ?? myCollectionId ?? "";
    if (!folder_id && (!folders || folders.length === 0)) {
      try {
        const newFolder = await postAddFolder({
          data: {
            name: isOnboarding ? "Starter Project" : "New Project",
            parent_id: null,
            description: "",
          },
        });
        folder_id = newFolder.id;
        setMyCollectionId(folder_id);
      } catch {
        // The backend can create a default folder when no destination exists.
      }
    }

    // Only the target project's settled snapshot can clear stored references.
    let cleanupVariables = folder_id
      ? getSettledSuccessfulQueryData<GlobalVariable[]>(
          queryClient,
          getGlobalVariablesQueryKey({ projectId: folder_id }),
        )
      : undefined;
    if (folder_id && cleanupVariables === undefined) {
      try {
        cleanupVariables = await queryClient.fetchQuery({
          queryKey: getGlobalVariablesQueryKey({ projectId: folder_id }),
          queryFn: () => fetchGlobalVariables({ projectId: folder_id }),
        });
      } catch {
        // Preserve references when the target project's snapshot is unavailable.
        cleanupVariables = undefined;
      }
    }
    const unavailableFields = cleanupVariables
      ? getUnavailableFields(cleanupVariables)
      : undefined;
    const globalVariablesEntries = cleanupVariables?.map(
      (variable) => variable.name,
    );

    const prepared: ReturnType<typeof createNewFlow>[] = [];
    for (const { flow, flowData } of normalized) {
      flowData?.nodes.forEach((node) => {
        updateGroupRecursion(
          node,
          flowData.edges,
          unavailableFields,
          globalVariablesEntries,
        );
      });
      // Every table of a new flow (an import, a template, a copy) is new, so
      // each row needs an id; rows that have one keep it.
      if (flowData) {
        flowData.nodes = withNodesTableRowIds(flowData.nodes);
      }
      const newFlow = createNewFlow(flowData!, folder_id, flow);
      newFlow.name = getFolderScopedDuplicateName(
        newFlow,
        flows ?? [],
        folder_id,
      );
      prepared.push(newFlow);
    }
    return prepared;
  };
};

export default usePrepareFlows;
