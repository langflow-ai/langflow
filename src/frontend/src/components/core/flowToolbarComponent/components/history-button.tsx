import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import useFlowStore from "@/stores/flowStore";
import FlowHistoryPanel from "@/pages/FlowPage/components/FlowHistoryPanel";
import { useState } from "react";

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
      {isOpen && currentFlow?.id && (
        <div className="fixed inset-y-0 right-0 z-50 shadow-xl">
          <FlowHistoryPanel
            flowId={currentFlow.id}
            onClose={() => setIsOpen(false)}
          />
        </div>
      )}
    </>
  );
};

export default HistoryButton;
