import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import useAddFlow from "@/hooks/flows/use-add-flow";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useFolderStore } from "@/stores/foldersStore";
import { updateIds } from "@/utils/reactflowUtils";
import { useParams } from "react-router-dom";


const KnowledgeBaseEmptyState = () => {
  const examples = useFlowsManagerStore((state) => state.examples);
  const addFlow = useAddFlow();
  const navigate = useCustomNavigate();
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);

  const folderIdUrl = folderId ?? myCollectionId;

  const handleCreateKnowledge = async () => {
    const knowledgeBasesExample = examples.find((example) => 
      example.name === "Knowledge Bases"
    );

    if (knowledgeBasesExample && knowledgeBasesExample.data) {
      updateIds(knowledgeBasesExample.data);
      addFlow({ flow: knowledgeBasesExample }).then((id) => {
        navigate(`/flow/${id}/folder/${folderIdUrl}`);
      });
      track("New Flow Created", { template: `${knowledgeBasesExample.name} Template` });
    }
  };


  return (
    <div className="flex h-full w-full flex-col items-center justify-center gap-8 pb-8">
      <div className="flex flex-col items-center gap-2">
        <h3 className="text-2xl font-semibold">No knowledge bases</h3>
        <p className="text-lg text-secondary-foreground">
          Create your first knowledge base to get started.
        </p>
      </div>
      <div className="flex items-center gap-2">
        <Button
          onClick={handleCreateKnowledge}
          className="!px-3 md:!px-4 md:!pl-3.5"
        >
          <ForwardedIconComponent
            name="Plus"
            aria-hidden="true"
            className="h-4 w-4"
          />
          <span className="whitespace-nowrap font-semibold">
            Create Knowledge
          </span>
        </Button>
      </div>
    </div>
  );
};

export default KnowledgeBaseEmptyState;
