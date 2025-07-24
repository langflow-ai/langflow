import { Button } from "@/components/ui/button";
import ForwardedIconComponent from "@/components/common/genericIconComponent";

interface KnowledgeBaseEmptyStateProps {
  onCreateKnowledgeBase?: () => void;
}

const KnowledgeBaseEmptyState = ({
  onCreateKnowledgeBase,
}: KnowledgeBaseEmptyStateProps) => {
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
          onClick={onCreateKnowledgeBase}
          disabled={!onCreateKnowledgeBase}
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
