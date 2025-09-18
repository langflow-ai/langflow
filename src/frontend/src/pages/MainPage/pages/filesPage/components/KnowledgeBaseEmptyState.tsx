import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";

const KnowledgeBaseEmptyState = ({
  handleCreateKnowledge,
}: {
  handleCreateKnowledge: () => void;
}) => {
  return (
    <div className="flex h-full w-full flex-col items-center justify-center gap-8 pb-8">
      <div className="flex flex-col items-center gap-2">
        <h3 className="text-2xl font-semibold">No knowledge bases</h3>
        <p className="text-lg text-secondary-foreground">
          Start with a knowledge base flow.
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
            Create Knowledge Base
          </span>
        </Button>
      </div>
    </div>
  );
};

export default KnowledgeBaseEmptyState;
