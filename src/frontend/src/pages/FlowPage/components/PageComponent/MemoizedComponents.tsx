import { Background, Panel } from "@xyflow/react";
import { memo } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import CanvasControlButton from "@/components/core/canvasControlsComponent/CanvasControlButton";
import CanvasControls from "@/components/core/canvasControlsComponent/CanvasControls";
import LogCanvasControls from "@/components/core/logCanvasControlsComponent";
import { Button } from "@/components/ui/button";
import { SidebarTrigger, useSidebar } from "@/components/ui/sidebar";
import { ENABLE_NEW_SIDEBAR } from "@/customization/feature-flags";
import { cn } from "@/utils/utils";
import { useSearchContext } from "../flowSidebarComponent";
import { NAV_ITEMS } from "../flowSidebarComponent/components/sidebarSegmentedNav";

export const MemoizedBackground = memo(() => (
  <Background size={2} gap={20} className="" />
));

interface MemoizedCanvasControlsProps {
  setIsAddingNote: (value: boolean) => void;
  position: { x: number; y: number };
  shadowBoxWidth: number;
  shadowBoxHeight: number;
}

export const MemoizedLogCanvasControls = memo(() => <LogCanvasControls />);

export const MemoizedCanvasControls = memo(
  ({
    setIsAddingNote,
    position,
    shadowBoxWidth,
    shadowBoxHeight,
  }: MemoizedCanvasControlsProps) => (
    <CanvasControls>
      <Button
        variant="ghost"
        size="icon"
        data-testid="add_note"
        className="group flex items-center justify-center px-2 rounded-none"
        title="Add sticky note"
        onClick={(e) => {
          e.stopPropagation();
          setIsAddingNote(true);
          const shadowBox = document.getElementById("shadow-box");
          if (shadowBox) {
            shadowBox.style.display = "block";
            shadowBox.style.left = `${position.x - shadowBoxWidth / 2}px`;
            shadowBox.style.top = `${position.y - shadowBoxHeight / 2}px`;
          }
        }}
      >
        <ForwardedIconComponent
          name="sticky-note"
          className="!h-5 !w-5 text-muted-foreground group-hover:text-primary"
        />
      </Button>
    </CanvasControls>
  ),
);

export const MemoizedSidebarTrigger = memo(() => {
  const { open, toggleSidebar, setActiveSection } = useSidebar();
  const { focusSearch, isSearchFocused } = useSearchContext();
  if (ENABLE_NEW_SIDEBAR) {
    return (
      <Panel
        className={cn(
          "react-flow__controls !top-auto !m-2 flex gap-1.5 rounded-md border border-secondary-hover bg-background p-0.5 text-primary shadow transition-all duration-300 [&>button]:border-0 [&>button]:bg-background hover:[&>button]:bg-accent",
          "pointer-events-auto opacity-100 group-data-[open=true]/sidebar-wrapper:pointer-events-none group-data-[open=true]/sidebar-wrapper:-translate-x-full group-data-[open=true]/sidebar-wrapper:opacity-0",
        )}
        position="top-left"
      >
        {NAV_ITEMS.map((item) => (
          <CanvasControlButton
            data-testid={`sidebar-trigger-${item.id}`}
            iconName={item.icon}
            iconClasses={item.id === "mcp" ? "h-8 w-8" : ""}
            tooltipText={item.tooltip}
            onClick={() => {
              setActiveSection(item.id);
              if (!open) {
                toggleSidebar();
              }
              if (item.id === "search") {
                // Add a small delay to ensure the sidebar is open and input is rendered
                setTimeout(() => focusSearch(), 100);
              }
            }}
            testId={item.id}
          />
        ))}
      </Panel>
    );
  }

  return (
    <Panel
      className={cn(
        "react-flow__controls !top-auto !m-2 flex gap-1.5 rounded-md border border-secondary-hover bg-background p-1.5 text-primary shadow transition-all duration-300 [&>button]:border-0 [&>button]:bg-background hover:[&>button]:bg-accent",
        "pointer-events-auto opacity-100 group-data-[open=true]/sidebar-wrapper:pointer-events-none group-data-[open=true]/sidebar-wrapper:-translate-x-full group-data-[open=true]/sidebar-wrapper:opacity-0",
      )}
      position="top-left"
    >
      <SidebarTrigger className="h-fit w-fit px-3 py-1.5">
        <ForwardedIconComponent name="PanelRightClose" className="h-4 w-4" />
        <span className="text-foreground">Components</span>
      </SidebarTrigger>
    </Panel>
  );
});
