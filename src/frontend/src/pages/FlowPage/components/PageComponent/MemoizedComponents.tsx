import { Background, Panel } from "@xyflow/react";
import { memo } from "react";
import { useTranslation } from "react-i18next";
import { useShallow } from "zustand/react/shallow";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import CanvasControlButton from "@/components/core/canvasControlsComponent/CanvasControlButton";
import CanvasControls from "@/components/core/canvasControlsComponent/CanvasControls";
import { SidebarTrigger, useSidebar } from "@/components/ui/sidebar";
import { ENABLE_NEW_SIDEBAR } from "@/customization/feature-flags";
import useFlowStore from "@/stores/flowStore";
import { AllNodeType } from "@/types/flow";
import { cn } from "@/utils/utils";
import { NAV_ITEMS } from "../flowSidebarComponent/components/sidebarSegmentedNav";

export const MemoizedBackground = memo(() => (
  <Background id="main-canvas-bg" size={2} gap={20} className="" />
));

interface MemoizedCanvasControlsProps {
  selectedNode: AllNodeType | null;
  isAgentWorking?: boolean;
}

export const MemoizedCanvasControls = memo(
  ({ selectedNode, isAgentWorking }: MemoizedCanvasControlsProps) => {
    const currentFlow = useFlowStore(useShallow((state) => state.currentFlow));
    const isLocked = currentFlow?.locked ?? false;
    const effectiveLocked = isLocked || isAgentWorking;

    return (
      <CanvasControls
        selectedNode={selectedNode}
        effectiveLocked={effectiveLocked}
      />
    );
  },
);

export const MemoizedSidebarTrigger = memo(() => {
  const { t } = useTranslation();
  const { open, toggleSidebar, setActiveSection } = useSidebar();
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
        <span className="text-foreground">{t("store.storeComponents")}</span>
      </SidebarTrigger>
    </Panel>
  );
});
