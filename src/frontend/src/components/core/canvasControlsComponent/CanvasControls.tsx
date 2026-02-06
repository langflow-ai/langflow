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
      className="react-flow__controls !bottom-4 flex !flex-row items-center gap-1 rounded-lg bg-background px-2 py-1 fill-foreground stroke-foreground text-primary [&>button]:border-0"
      position="bottom-center"
    >
      <div className="group relative">
        <span className="absolute -top-4 -left-1 z-10 flex items-center gap-0.5 rounded bg-pink-600 px-1 py-0.5 text-[9px] font-medium leading-none text-white opacity-0 scale-90 transition-all duration-200 group-hover:opacity-100 group-hover:scale-100">
          <ForwardedIconComponent name="Sparkles" className="h-2.5 w-2.5" />
          New
        </span>
        <Button
          unstyled
          size="icon"
          className="flex h-8 w-8 items-center justify-center overflow-hidden rounded-md hover:bg-muted"
          title="Langflow Assistant"
          onClick={handleAssistantClick}
        >
          {/* Muted icon - normal state */}
          <svg
            width="18"
            height="18"
            viewBox="0 0 16 16"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className="text-muted-foreground group-hover:hidden"
          >
            <path
              d="M2.1665 11.3333H3.83317L7.1665 8H8.83317L12.1665 4.66667H13.8332M7.1665 13H8.83317L12.1665 9.66667H13.8332M2.1665 6.33333H3.83317L7.1665 3H8.83317"
              stroke="currentColor"
              strokeWidth="1.11111"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          {/* Colorful icon - hover state */}
          <img
            src={langflowAssistantIcon}
            alt="Langflow Assistant"
            className="hidden h-full w-full object-cover group-hover:block"
          />
        </Button>
      </div>
      <Button
        unstyled
        size="icon"
        className="group flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted"
        title="Undo"
        onClick={undo}
      >
        <ForwardedIconComponent
          name="Undo2"
          className="h-[18px] w-[18px] text-muted-foreground group-hover:text-foreground"
        />
      </Button>
      <Button
        unstyled
        size="icon"
        className="group flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted"
        title="Redo"
        onClick={redo}
      >
        <ForwardedIconComponent
          name="Redo2"
          className="h-[18px] w-[18px] text-muted-foreground group-hover:text-foreground"
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
