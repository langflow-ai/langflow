import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import useFlowStore from "@/stores/flowStore";
import FlowHistoryPanel from "@/pages/FlowPage/components/FlowHistoryPanel";
import { useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

const HistoryButton = () => {
  const [isOpen, setIsOpen] = useState(false);
  const currentFlow = useFlowStore((state) => state.currentFlow);

  // Safety-net: disable auto-save and inspection panel while history is open.
  // This lives in the parent so that even if FlowHistoryPanel crashes during
  // render, the cleanup still fires when isOpen becomes false.
  const autoSaveFnRef = useRef<any>(null);
  const inspectionPanelWasVisible = useRef(false);
  useLayoutEffect(() => {
    if (!isOpen) return;

    const currentAutoSave = useFlowStore.getState().autoSaveFlow;
    if (currentAutoSave) {
      autoSaveFnRef.current = currentAutoSave;
      // Flush any pending debounced save so the DB captures the latest draft
      // changes before we start swapping store state for previews.
      if (typeof currentAutoSave.flush === "function") {
        try {
          currentAutoSave.flush();
        } catch (err) {
          console.warn("HistoryButton: failed to flush auto-save:", err);
        }
      }
      useFlowStore.setState({ autoSaveFlow: undefined });
    }

    inspectionPanelWasVisible.current =
      useFlowStore.getState().inspectionPanelVisible;
    if (inspectionPanelWasVisible.current) {
      useFlowStore.setState({ inspectionPanelVisible: false });
    }

    return () => {
      if (autoSaveFnRef.current) {
        useFlowStore.setState({ autoSaveFlow: autoSaveFnRef.current });
        autoSaveFnRef.current = null;
      }
      if (inspectionPanelWasVisible.current) {
        useFlowStore.setState({ inspectionPanelVisible: true });
        inspectionPanelWasVisible.current = false;
      }
    };
  }, [isOpen]);

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
