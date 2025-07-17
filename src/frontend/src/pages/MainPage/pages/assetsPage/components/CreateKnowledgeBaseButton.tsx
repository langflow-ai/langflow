import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import useAlertStore from "@/stores/alertStore";

interface CreateKnowledgeBaseButtonProps {
  onCreateKnowledgeBase?: () => void;
}

const CreateKnowledgeBaseButton = ({
  onCreateKnowledgeBase,
}: CreateKnowledgeBaseButtonProps) => {
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  const handleClick = () => {
    if (onCreateKnowledgeBase) {
      onCreateKnowledgeBase();
    } else {
      // TODO: Implement create knowledge base functionality
      setSuccessData({
        title: "Knowledge Base creation coming soon!",
      });
    }
  };

  return (
    <ShadTooltip content="Create Knowledge Base" side="bottom">
      <Button
        className="!px-3 md:!px-4 md:!pl-3.5"
        onClick={handleClick}
        id="create-kb-btn"
        data-testid="create-kb-btn"
      >
        <ForwardedIconComponent
          name="Plus"
          aria-hidden="true"
          className="h-4 w-4"
        />
        <span className="hidden whitespace-nowrap font-semibold md:inline">
          Create KB
        </span>
      </Button>
    </ShadTooltip>
  );
};

export default CreateKnowledgeBaseButton;
