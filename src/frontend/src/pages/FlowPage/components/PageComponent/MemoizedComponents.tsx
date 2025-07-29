import { default as ForwardedIconComponent, default as IconComponent } from "@/components/common/genericIconComponent";
import CanvasControls from "@/components/core/canvasControlsComponent";
import LogCanvasControls from "@/components/core/logCanvasControlsComponent";
import { Button } from "@/components/ui/button";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { cn } from "@/utils/utils";
import { Background, Panel } from "@xyflow/react";
import { memo } from "react";

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
        className="group rounded flex items-center justify-center ml-1"

        onClick={() => {
          setIsAddingNote(true);
          const shadowBox = document.getElementById("shadow-box");
          if (shadowBox) {
            shadowBox.style.display = "block";
            shadowBox.style.left = `${position.x - shadowBoxWidth / 2}px`;
            shadowBox.style.top = `${position.y - shadowBoxHeight / 2}px`;
          }
        }}
      >
        <IconComponent name="sticky-note" className="!h-5 !w-5 text-muted-foreground group-hover:text-primary" />
      </Button>

    </CanvasControls>
  ),
);

export const MemoizedSidebarTrigger = memo(() => (
  <Panel
    className={cn(
      "react-flow__controls !top-auto !m-2 flex gap-1.5 rounded-md border border-secondary-hover bg-background fill-foreground stroke-foreground p-1.5 text-primary shadow transition-all duration-300 [&>button]:border-0 [&>button]:bg-background hover:[&>button]:bg-accent",
      "pointer-events-auto opacity-100 group-data-[open=true]/sidebar-wrapper:pointer-events-none group-data-[open=true]/sidebar-wrapper:-translate-x-full group-data-[open=true]/sidebar-wrapper:opacity-0",
    )}
    position="top-left"
  >
    <SidebarTrigger className="h-fit w-fit px-3 py-1.5">
      <ForwardedIconComponent name="PanelRightClose" className="h-4 w-4" />
      <span className="text-foreground">Components</span>
    </SidebarTrigger>
  </Panel>
));
