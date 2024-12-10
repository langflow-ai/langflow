import { usePostAddFlow } from "@/controllers/API/queries/flows/use-post-add-flow";
import { useFolderStore } from "@/stores/foldersStore";
import { addVersionToDuplicates, createNewFlow } from "@/utils/reactflowUtils";
import { useParams } from "react-router-dom";

type UseDuplicateFlowsParams = {
  selectedFlowsComponentsCards: string[];
  allFlows: any[];
  setSuccessData: (data: { title: string }) => void;
};

const useDuplicateFlows = ({
  selectedFlowsComponentsCards,
  allFlows,
  setSuccessData,
}: UseDuplicateFlowsParams) => {
  const { mutateAsync: postAddFlow } = usePostAddFlow();
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);

  const handleDuplicate = async () => {
    selectedFlowsComponentsCards.map(async (selectedFlow) => {
      const currentFlow = allFlows.find((flow) => flow.id === selectedFlow);
      const folder_id = folderId ?? myCollectionId ?? "";

      const flowsToCheckNames = allFlows?.filter(
        (f) => f.folder_id === folder_id,
      );

      const newFlow = createNewFlow(currentFlow.data, folder_id, currentFlow);

      const newName = addVersionToDuplicates(newFlow, flowsToCheckNames ?? []);
      newFlow.name = newName;
      newFlow.folder_id = folder_id;

      await postAddFlow(newFlow);
      setSuccessData({
        title: `${newFlow.is_component ? "Component" : "Flow"} duplicated successfully`,
      });
    });
  };

  return { handleDuplicate };
};

export default useDuplicateFlows;
