import { Panel, useStoreApi } from "@xyflow/react";
import { type ReactNode, useCallback, useEffect, useState } from "react";
import { useShallow } from "zustand/react/shallow";
import langflowAssistantIcon from "@/assets/langflow_assistant.svg";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { ENABLE_INSPECTION_PANEL } from "@/customization/feature-flags";
import useAssistantManagerStore from "@/stores/assistantManagerStore";
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
  const setAssistantSidebarOpen = useAssistantManagerStore(
    (state) => state.setAssistantSidebarOpen,
  );
  const assistantSidebarOpen = useAssistantManagerStore(
    (state) => state.assistantSidebarOpen,
  );
  const inspectionPanelVisible = useFlowStore(
    (state) => state.inspectionPanelVisible,
  );
  const setInspectionPanelVisible = useFlowStore(
    (state) => state.setInspectionPanelVisible,
  );

  const handleAssistantClick = () => {
    setAssistantSidebarOpen(!assistantSidebarOpen);
  };

  const [isAddNoteActive, setIsAddNoteActive] = useState(false);

  const handleAddNote = useCallback(() => {
    window.dispatchEvent(new Event("lf:start-add-note"));
    setIsAddNoteActive(true);
  }, []);

  useEffect(() => {
    const onEnd = () => setIsAddNoteActive(false);
    window.addEventListener("lf:end-add-note", onEnd);
    return () => window.removeEventListener("lf:end-add-note", onEnd);
  }, []);

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
        className="react-flow__controls flex !flex-row items-center gap-1 !overflow-visible rounded-lg bg-background px-2 py-1 fill-foreground stroke-foreground text-primary [&>button]:border-0"
        position="bottom-center"
      >
        <div className="group relative">
          <span
            className={`absolute -top-4 -left-1 z-10 flex items-center gap-0.5 rounded bg-pink-600 px-1 py-0.5 text-[9px] font-medium leading-none text-white transition-all duration-200 ${assistantSidebarOpen ? "hidden" : "opacity-0 scale-90 group-hover:opacity-100 group-hover:scale-100"}`}
          >
            <ForwardedIconComponent name="Sparkles" className="h-2.5 w-2.5" />
            New
          </span>
          <Button
            unstyled
            size="icon"
            data-testid="assistant-button"
            className="relative flex h-8 w-8 items-center justify-center overflow-hidden rounded-md hover:bg-muted"
            onClick={handleAssistantClick}
          >
            {/* Muted icon - normal state */}
            <svg
              width="18"
              height="18"
              viewBox="0 0 16 16"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              className="absolute inset-0 m-auto text-muted-foreground transition-opacity duration-150 group-hover:opacity-0"
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
              className="absolute inset-0 h-full w-full object-cover opacity-0 transition-opacity duration-150 group-hover:opacity-100"
            />
          </Button>
        </div>
        <CanvasControlsDropdown selectedNode={selectedNode} />
        <Button
          unstyled
          size="icon"
          data-testid="canvas-add-note-button"
          className="group flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted"
          title="Add Sticky Note"
          onClick={handleAddNote}
        >
          <ForwardedIconComponent
            name="sticky-note"
            className={`h-[18px] w-[18px] transition-colors ${
              isAddNoteActive
                ? "text-foreground"
                : "text-muted-foreground group-hover:text-foreground"
            }`}
          />
        </Button>
        <HelpDropdown />
        {children}
        {ENABLE_INSPECTION_PANEL && (
          <Button
            unstyled
            size="icon"
            data-testid="canvas_controls_toggle_inspector"
            className="group flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted"
            title={
              !selectedNode
                ? "Select a node to open the Inspector Panel"
                : inspectionPanelVisible
                  ? "Hide Inspector Panel"
                  : "Show Inspector Panel"
            }
            onClick={() => setInspectionPanelVisible(!inspectionPanelVisible)}
          >
            <ForwardedIconComponent
              name={inspectionPanelVisible ? "PanelRightClose" : "PanelRight"}
              className="!h-5 !w-5 text-muted-foreground group-hover:text-foreground"
            />
          </Button>
        )}
      </Panel>
    </>
  );
};

export default CanvasControls;
