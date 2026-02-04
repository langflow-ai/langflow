import { Panel, useStoreApi } from "@xyflow/react";
import { type ReactNode, useEffect } from "react";
import { useShallow } from "zustand/react/shallow";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ENABLE_INSPECTION_PANEL } from "@/customization/feature-flags";
import useFlowStore from "@/stores/flowStore";
import CanvasControlsDropdown from "./CanvasControlsDropdown";
import HelpDropdown from "./HelpDropdown";
import { AllNodeType } from "@/types/flow";

const CanvasControls = ({
  children,
  selectedNode,
}: {
  children?: ReactNode;
  selectedNode: AllNodeType | null;
}) => {
  const reactFlowStoreApi = useStoreApi();
  const isFlowLocked = useFlowStore(
    useShallow((state) => state.currentFlow?.locked),
  );
  const inspectionPanelVisible = useFlowStore(
    (state) => state.inspectionPanelVisible,
  );
  const setInspectionPanelVisible = useFlowStore(
    (state) => state.setInspectionPanelVisible,
  );

  useEffect(() => {
    reactFlowStoreApi.setState({
      nodesDraggable: !isFlowLocked,
      nodesConnectable: !isFlowLocked,
      elementsSelectable: !isFlowLocked,
    });
  }, [isFlowLocked, reactFlowStoreApi]);

  return (
    <>
      <Panel
        data-testid="main_canvas_controls"
        className="react-flow__controls !m-2 flex !flex-row rounded-md border border-border bg-background fill-foreground stroke-foreground text-primary [&>button]:border-0"
        position="bottom-left"
      >
        {children}
        {children && (
          <span>
            <Separator orientation="vertical" />
          </span>
        )}
        <CanvasControlsDropdown selectedNode={selectedNode} />
        <span>
          <Separator orientation="vertical" />
        </span>
        <HelpDropdown />
      </Panel>
      {ENABLE_INSPECTION_PANEL && (
        <Panel
          data-testid="inspector_toggle_panel"
          className="react-flow__controls !m-2 flex !flex-row rounded-md border border-border bg-background fill-foreground stroke-foreground text-primary [&>button]:border-0"
          position="bottom-right"
        >
          <Button
            variant="ghost"
            size="icon"
            data-testid="inspector-toggle"
            className="group flex items-center justify-center px-2 rounded-none"
            title={`Inspector Panel: ${inspectionPanelVisible ? "Enabled" : "Disabled"}`}
            onClick={() => setInspectionPanelVisible(!inspectionPanelVisible)}
          >
            <ForwardedIconComponent
              name={inspectionPanelVisible ? "PanelRightOpen" : "PanelRightClose"}
              aria-hidden="true"
              className="text-muted-foreground group-hover:text-primary !h-5 !w-5"
            />
          </Button>
        </Panel>
      )}
    </>
  );
};

export default CanvasControls;
