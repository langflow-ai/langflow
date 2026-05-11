import { Background, Panel } from "@xyflow/react";
import { cloneDeep } from "lodash";
import { memo, useCallback, useState } from "react";
import { useShallow } from "zustand/react/shallow";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import CanvasControlButton from "@/components/core/canvasControlsComponent/CanvasControlButton";
import CanvasControls from "@/components/core/canvasControlsComponent/CanvasControls";
import { Button } from "@/components/ui/button";
import { SidebarTrigger, useSidebar } from "@/components/ui/sidebar";
import { ENABLE_NEW_SIDEBAR } from "@/customization/feature-flags";
import useSaveFlow from "@/hooks/flows/use-save-flow";
import useFlowStore from "@/stores/flowStore";
import { AllNodeType } from "@/types/flow";
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
  selectedNode: AllNodeType | null;
  isAgentWorking?: boolean;
}

export const MemoizedCanvasControls = memo(
  ({
    setIsAddingNote,
    shadowBoxWidth,
    shadowBoxHeight,
    selectedNode,
    isAgentWorking,
  }: MemoizedCanvasControlsProps) => {
    const currentFlow = useFlowStore(useShallow((state) => state.currentFlow));
    const setCurrentFlow = useFlowStore((state) => state.setCurrentFlow);
    const saveFlow = useSaveFlow();
    const isLocked = currentFlow?.locked ?? false;
    const effectiveLocked = isLocked || isAgentWorking;
    const [isSaving, setIsSaving] = useState(false);

    const handleToggleLock = useCallback(async () => {
      if (isAgentWorking || isSaving || !currentFlow) return;
      const newFlow = cloneDeep(currentFlow);
      newFlow.locked = !isLocked;
      setIsSaving(true);
      try {
        await saveFlow(newFlow);
        setCurrentFlow(newFlow);
      } finally {
        setIsSaving(false);
      }
    }, [
      currentFlow,
      isLocked,
      isAgentWorking,
      isSaving,
      saveFlow,
      setCurrentFlow,
    ]);

    return (
      <CanvasControls
        selectedNode={selectedNode}
        effectiveLocked={effectiveLocked}
      >
        <Button
          unstyled
          size="icon"
          data-testid="lock-status"
          disabled={isAgentWorking || isSaving}
          className={cn(
            "flex items-center justify-center px-2 rounded-none gap-1",
            isAgentWorking || isSaving
              ? "cursor-default opacity-70"
              : "cursor-pointer",
          )}
          title={
            isAgentWorking
              ? "Agent Working"
              : isSaving
                ? "Saving..."
                : isLocked
                  ? "Unlock flow"
                  : "Lock flow"
          }
          onClick={handleToggleLock}
        >
          <ForwardedIconComponent
            name={effectiveLocked ? "Lock" : "Unlock"}
            className={cn(
              "!h-[18px] !w-[18px] text-muted-foreground",
              effectiveLocked && "text-destructive",
            )}
          />
          {effectiveLocked && (
            <span className="text-xs text-destructive">
              {isAgentWorking ? "Agent Working" : "Flow Locked"}
            </span>
          )}
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
            key={item.id}
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
