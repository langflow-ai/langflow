import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import useFlowStore from "@/stores/flowStore";
import FlowHistoryPanel from "@/pages/FlowPage/components/FlowHistoryPanel";
import { useState } from "react";
import { createPortal } from "react-dom";

const HistoryButton = () => {
  const [isOpen, setIsOpen] = useState(false);
  const currentFlow = useFlowStore((state) => state.currentFlow);

  return (
    <>
      <ShadTooltip content="Version History">
        <div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setIsOpen((prev) => !prev)}
            data-testid="history-btn-flow"
            className="relative h-8 w-8"
          >
            <ForwardedIconComponent name="History" className="h-4 w-4" />
          </Button>
        </div>
      </ShadTooltip>
      {isOpen &&
        currentFlow?.id &&
        createPortal(
          <FlowHistoryPanel
            flowId={currentFlow.id}
            onClose={() => setIsOpen(false)}
          />,
          document.body,
        )}
    </>
  );
};

export default HistoryButton;
