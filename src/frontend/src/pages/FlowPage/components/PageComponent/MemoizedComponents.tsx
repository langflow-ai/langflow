import { Background, Panel } from "@xyflow/react";
import { memo, useEffect, useState } from "react";
import { useShallow } from "zustand/react/shallow";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import CanvasControlButton from "@/components/core/canvasControlsComponent/CanvasControlButton";
import CanvasControls from "@/components/core/canvasControlsComponent/CanvasControls";
import LogCanvasControls from "@/components/core/logCanvasControlsComponent";
import { Button } from "@/components/ui/button";
import { SidebarTrigger, useSidebar } from "@/components/ui/sidebar";
import { ENABLE_NEW_SIDEBAR } from "@/customization/feature-flags";
import useFlowStore from "@/stores/flowStore";
import { cn } from "@/utils/utils";
import { useSearchContext } from "../flowSidebarComponent";
import { NAV_ITEMS } from "../flowSidebarComponent/components/sidebarSegmentedNav";

export const MemoizedBackground = memo(() => (
  <Background size={2} gap={20} className="" />
));

interface MemoizedCanvasControlsProps {
  setIsAddingNote: (value: boolean) => void;
  shadowBoxWidth: number;
  shadowBoxHeight: number;
}

export const MemoizedLogCanvasControls = memo(() => <LogCanvasControls />);

export const MemoizedCanvasControls = memo(
  ({
    setIsAddingNote,
    shadowBoxWidth,
    shadowBoxHeight,
  }: MemoizedCanvasControlsProps) => {
    const isLocked = useFlowStore(
      useShallow((state) => state.currentFlow?.locked),
    );
    const deploymentStatus = useFlowStore(
      useShallow((state) => state.currentFlow?.status),
    );
    const isDeployed = deploymentStatus === "DEPLOYED";

    const [showDeployedText, setShowDeployedText] = useState(false);
    const [showLockedText, setShowLockedText] = useState(false);

    // Show text briefly when state changes
    useEffect(() => {
      if (isDeployed) {
        setShowDeployedText(true);
        const timer = setTimeout(() => setShowDeployedText(false), 2000);
        return () => clearTimeout(timer);
      }
    }, [isDeployed]);

    useEffect(() => {
      if (isLocked) {
        setShowLockedText(true);
        const timer = setTimeout(() => setShowLockedText(false), 2000);
        return () => clearTimeout(timer);
      }
    }, [isLocked]);

    return (
      <CanvasControls>
        <Button
          unstyled
          unselectable="on"
          size="icon"
          data-testid="deployment-status-indicator"
          className="flex items-center justify-center px-2 rounded-none gap-1 cursor-default group"
          title={isDeployed ? "Flow is deployed" : "Flow is in draft mode"}
          onMouseEnter={() => isDeployed && setShowDeployedText(true)}
          onMouseLeave={() => isDeployed && setShowDeployedText(false)}
        >
          <ForwardedIconComponent
            name="Rocket"
            className={cn(
              "!h-[18px] !w-[18px] transition-colors duration-200",
              isDeployed ? "text-success" : "text-muted-foreground opacity-50",
            )}
          />
          <span
            className={cn(
              "text-xs text-success transition-all duration-200 ease-in-out whitespace-nowrap overflow-hidden",
              showDeployedText && isDeployed
                ? "max-w-[100px] opacity-100"
                : "max-w-0 opacity-0",
            )}
          >
            Deployed
          </span>
        </Button>
        <Button
          unstyled
          unselectable="on"
          size="icon"
          data-testid="lock-status"
          className="flex items-center justify-center px-2 rounded-none gap-1 cursor-default overflow-hidden group"
          title={`Lock status: ${isLocked ? "Locked" : "Unlocked"}`}
          onMouseEnter={() => isLocked && setShowLockedText(true)}
          onMouseLeave={() => isLocked && setShowLockedText(false)}
        >
          <ForwardedIconComponent
            name={isLocked ? "Lock" : "Unlock"}
            className={cn(
              "!h-[18px] !w-[18px] text-muted-foreground transition-colors duration-200",
              isLocked && "text-destructive",
            )}
          />
          <span
            className={cn(
              "text-xs text-destructive transition-all duration-200 ease-in-out whitespace-nowrap overflow-hidden",
              showLockedText && isLocked
                ? "max-w-[100px] opacity-100"
                : "max-w-0 opacity-0",
            )}
          >
            Flow Locked
          </span>
        </Button>
      </CanvasControls>
    );
  },
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
