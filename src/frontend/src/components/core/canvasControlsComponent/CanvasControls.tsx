import { Panel, useStoreApi } from "@xyflow/react";
import { type ReactNode, useEffect } from "react";
import { useShallow } from "zustand/react/shallow";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ENABLE_INSPECTION_PANEL } from "@/customization/feature-flags";
import useFlowStore from "@/stores/flowStore";
import type { AllNodeType } from "@/types/flow";
import CanvasControlsDropdown from "./CanvasControlsDropdown";
import HelpDropdown from "./HelpDropdown";

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
          data-testid="canvas_controls_inspector"
          className="react-flow__controls !left-auto !m-2 flex !flex-row rounded-md border border-border bg-background fill-foreground stroke-foreground text-primary [&>button]:border-0"
          position="bottom-right"
        >
          <Button
            unstyled
            size="icon"
            data-testid="canvas_controls_toggle_inspector"
            className={`group rounded-none px-2 py-2 flex items-center justify-center disabled:pointer-events-none disabled:opacity-50 ${inspectionPanelVisible ? "bg-accent" : "hover:bg-muted"}`}
            title={
              !selectedNode
                ? "Select a node to open the Inspector Panel"
                : inspectionPanelVisible
                  ? "Hide Inspector Panel"
                  : "Show Inspector Panel"
            }
            disabled={!selectedNode}
            onClick={() => setInspectionPanelVisible(!inspectionPanelVisible)}
          >
            <ForwardedIconComponent
              name={inspectionPanelVisible ? "PanelRightClose" : "PanelRight"}
              className={`${inspectionPanelVisible ? "text-primary" : "text-muted-foreground group-hover:text-primary"} !h-5 !w-5`}
            />
          </Button>
        </Panel>
      )}
    </>
  );
};

export default CanvasControls;
