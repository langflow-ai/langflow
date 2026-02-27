import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import Loading from "@/components/ui/loading";
import KnowledgeBaseUploadModal from "@/modals/knowledgeBaseUploadModal/KnowledgeBaseUploadModal";
import useAlertStore from "@/stores/alertStore";

const KnowledgeBaseEmptyState = ({
  handleCreateKnowledge,
}: {
  handleCreateKnowledge: () => void;
}) => {
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const queryClient = useQueryClient();

  if (isCreating) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center gap-3">
        <Loading size={36} />
        <span className="text-sm text-muted-foreground pt-3">
          Setting up your knowledge base...
        </span>
      </div>
    );
  }

  return (
    <div className="flex h-full w-full flex-col items-center justify-center gap-8 pb-8">
      <div className="flex flex-col items-center gap-2">
        <h3 className="text-2xl font-semibold">No knowledge bases</h3>
        <p className="text-lg text-secondary-foreground">
          Create powerful AI experiences by connecting your documents to
          intelligent workflows.
        </p>
      </div>
      <div className="flex items-center gap-2">
        <Button
          className="flex items-center gap-2 font-semibold"
          onClick={() => setIsUploadModalOpen(true)}
        >
          <ForwardedIconComponent name="Plus" className="h-4 w-4" />
          Add Knowledge
        </Button>
      </div>

      <KnowledgeBaseUploadModal
        open={isUploadModalOpen}
        setOpen={(open) => {
          setIsUploadModalOpen(open);
          if (!open) {
            setIsCreating(true);
            queryClient.invalidateQueries({
              queryKey: ["useGetKnowledgeBases"],
            });
          }
        }}
        onSubmit={(data) => {
          setSuccessData({
            title: `Knowledge base "${data.sourceName}" created`,
          });
        }}
      />
    </div>
  );
};

export default KnowledgeBaseEmptyState;
