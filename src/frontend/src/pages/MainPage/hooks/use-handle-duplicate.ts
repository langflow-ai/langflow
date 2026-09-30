import { useParams } from "react-router-dom";
import { usePostAddFlow } from "@/controllers/API/queries/flows/use-post-add-flow";
import { useFolderStore } from "@/stores/foldersStore";
import type { FlowType } from "@/types/flow";
import { createNewFlow } from "@/utils/reactflowUtils";

type UseDuplicateFlowsParams = {
  flow?: FlowType;
};

const useDuplicateFlow = ({ flow }: UseDuplicateFlowsParams) => {
  const { mutateAsync: postAddFlow } = usePostAddFlow();
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);

  const handleDuplicate = async () => {
    if (flow?.data) {
      const folder_id = folderId ?? myCollectionId ?? "";

      const newFlow = createNewFlow(flow.data, folder_id, flow);

      newFlow.folder_id = folder_id;

      await postAddFlow(newFlow);
    }
  };

  return { handleDuplicate };
};

export default useDuplicateFlow;
