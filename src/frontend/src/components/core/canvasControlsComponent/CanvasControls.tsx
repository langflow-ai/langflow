import { Panel, useStoreApi } from "@xyflow/react";
import { type ReactNode, useEffect } from "react";
import { useShallow } from "zustand/react/shallow";
import { Separator } from "@/components/ui/separator";
import useFlowStore from "@/stores/flowStore";
import CanvasControlsDropdown from "./CanvasControlsDropdown";
import HelpDropdown from "./HelpDropdown";

const CanvasControls = ({ children }: { children?: ReactNode }) => {
  const reactFlowStoreApi = useStoreApi();
  const isFlowLocked = useFlowStore(
    useShallow((state) => state.currentFlow?.locked),
  );

  useEffect(() => {
    reactFlowStoreApi.setState({
      nodesDraggable: !isFlowLocked,
      nodesConnectable: !isFlowLocked,
      elementsSelectable: !isFlowLocked,
    });
  }, [isFlowLocked, reactFlowStoreApi]);

  return (
    <Panel
      data-testid="main_canvas_controls"
      className="react-flow__controls !left-auto !m-2 flex !flex-row rounded-md border border-border bg-background fill-foreground stroke-foreground text-primary [&>button]:border-0"
      position="bottom-right"
    >
      {children}
      {children && (
        <span>
          <Separator orientation="vertical" />
        </span>
      )}
      <CanvasControlsDropdown />
      <span>
        <Separator orientation="vertical" />
      </span>
      <HelpDropdown />
    </Panel>
  );
};

export default CanvasControls;
