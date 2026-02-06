import { Panel, useStoreApi } from "@xyflow/react";
import { type ReactNode, useEffect } from "react";
import { useShallow } from "zustand/react/shallow";
import langflowAssistantIcon from "@/assets/langflow_assistant.svg";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import useAssistantManagerStore from "@/stores/assistantManagerStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
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
  const undo = useFlowsManagerStore((state) => state.undo);
  const redo = useFlowsManagerStore((state) => state.redo);
  const setAssistantSidebarOpen = useAssistantManagerStore(
    (state) => state.setAssistantSidebarOpen,
  );
  const assistantSidebarOpen = useAssistantManagerStore(
    (state) => state.assistantSidebarOpen,
  );

  const handleAssistantClick = () => {
    setAssistantSidebarOpen(!assistantSidebarOpen);
  };

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
      className="react-flow__controls !bottom-8 flex !flex-row items-center gap-1 rounded-lg bg-background px-2 py-1 fill-foreground stroke-foreground text-primary [&>button]:border-0"
      position="bottom-center"
    >
      <div className="relative">
        <span className="absolute -top-2.5 -left-1 z-10 rounded bg-pink-600 px-1 py-0.5 text-[9px] font-medium leading-none text-white">
          New
        </span>
        <Button
          unstyled
          size="icon"
          className="flex h-8 w-8 items-center justify-center overflow-hidden rounded-md hover:bg-muted"
          title="Langflow Assistant"
          onClick={handleAssistantClick}
        >
          <img
            src={langflowAssistantIcon}
            alt="Langflow Assistant"
            className="h-full w-full object-cover"
          />
        </Button>
      </div>
      <Button
        unstyled
        size="icon"
        className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted"
        title="Undo"
        onClick={undo}
      >
        <ForwardedIconComponent
          name="Undo2"
          className="h-[18px] w-[18px] text-muted-foreground"
        />
      </Button>
      <Button
        unstyled
        size="icon"
        className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted"
        title="Redo"
        onClick={redo}
      >
        <ForwardedIconComponent
          name="Redo2"
          className="h-[18px] w-[18px] text-muted-foreground"
        />
      </Button>
      <CanvasControlsDropdown selectedNode={selectedNode} />
      <span>
        <Separator orientation="vertical" />
      </span>
      <HelpDropdown />
      {children}
    </Panel>
  );
};

export default CanvasControls;
