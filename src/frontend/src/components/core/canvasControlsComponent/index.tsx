import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import useSaveFlow from "@/hooks/flows/use-save-flow";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useFlowStore from "@/stores/flowStore";
import { cn } from "@/utils/utils";
import {
  ControlButton,
  Panel,
  useReactFlow,
  useStore,
  useStoreApi,
  type ReactFlowState,
} from "@xyflow/react";
import { cloneDeep } from "lodash";
import { useCallback, useEffect, useRef, useState } from "react";
import { useShallow } from "zustand/react/shallow";
import { shallow } from "zustand/shallow";
import React from "react";

type CustomControlButtonProps = {
  iconName: string;
  tooltipText: string;
  onClick: () => void;
  disabled?: boolean;
  backgroundClasses?: string;
  iconClasses?: string;
  testId?: string;
};

export const CustomControlButton = ({
  iconName,
  tooltipText,
  onClick,
  disabled,
  backgroundClasses,
  iconClasses,
  testId,
}: CustomControlButtonProps): JSX.Element => {
  return (
    <ControlButton
      data-testid={testId}
      className="group !h-8 !w-8 rounded !p-0"
      onClick={onClick}
      disabled={disabled}
      title={testId?.replace(/_/g, " ")}
    >
      <ShadTooltip content={tooltipText} side="right">
        <div className={cn("rounded p-2.5", backgroundClasses)}>
          <IconComponent
            name={iconName}
            aria-hidden="true"
            className={cn(
              "scale-150 text-muted-foreground group-hover:text-primary",
              iconClasses,
            )}
          />
        </div>
      </ShadTooltip>
    </ControlButton>
  );
};

const selector = (s: ReactFlowState) => ({
  isInteractive: s.nodesDraggable || s.nodesConnectable || s.elementsSelectable,
  minZoomReached: s.transform[2] <= s.minZoom,
  maxZoomReached: s.transform[2] >= s.maxZoom,
});

const COLLAPSE_TIMEOUT = 10000; // ms

const ICON_SIZE = 40; // px, adjust if needed for your icon/button size

const CanvasControls = ({ children }) => {
  const store = useStoreApi();
  const { fitView, zoomIn, zoomOut } = useReactFlow();
  const { isInteractive, minZoomReached, maxZoomReached } = useStore(
    selector,
    shallow,
  );
  const saveFlow = useSaveFlow();
  const isLocked = useFlowStore(
    useShallow((state) => state.currentFlow?.locked),
  );
  const setCurrentFlow = useFlowStore((state) => state.setCurrentFlow);
  const autoSaving = useFlowsManagerStore((state) => state.autoSaving);
  const [collapsed, setCollapsed] = useState(true);
  const collapseTimer = useRef<NodeJS.Timeout | null>(null);

  // Animated wrapper logic
  const [maxHeight, setMaxHeight] = useState('40px');
  const contentRef = useRef<HTMLDivElement>(null);

  // Calculate number of visible buttons (4 default + real children if present)
  const numButtons = 4 + (children ? React.Children.toArray(children).filter(Boolean).length : 0);

  useEffect(() => {
    store.setState({
      nodesDraggable: !isLocked,
      nodesConnectable: !isLocked,
      elementsSelectable: !isLocked,
    });
  }, [isLocked]);

  useEffect(() => {
    if (!collapsed && contentRef.current) {
      setMaxHeight(contentRef.current.scrollHeight + 'px');
    } else {
      setMaxHeight('40px');
    }
  }, [collapsed, children]);

  const handleSaveFlow = useCallback(() => {
    const currentFlow = useFlowStore.getState().currentFlow;
    if (!currentFlow) return;
    const newFlow = cloneDeep(currentFlow);
    newFlow.locked = isInteractive;
    if (autoSaving) {
      saveFlow(newFlow);
    } else {
      setCurrentFlow(newFlow);
    }
  }, [isInteractive, autoSaving, saveFlow, setCurrentFlow]);

  const onToggleInteractivity = useCallback(() => {
    store.setState({
      nodesDraggable: !isInteractive,
      nodesConnectable: !isInteractive,
      elementsSelectable: !isInteractive,
    });
    handleSaveFlow();
  }, [isInteractive, store, handleSaveFlow]);

  // Expand on mouse enter
  const handleMouseEnter = () => {
    if (collapseTimer.current) {
      clearTimeout(collapseTimer.current);
      collapseTimer.current = null;
    }
    setCollapsed(false);
  };

  // Collapse after timeout on mouse leave
  const handleMouseLeave = () => {
    if (collapseTimer.current) clearTimeout(collapseTimer.current);
    collapseTimer.current = setTimeout(() => {
      setCollapsed(true);
    }, COLLAPSE_TIMEOUT);
  };

  // Clean up timer on unmount
  useEffect(() => {
    return () => {
      if (collapseTimer.current) clearTimeout(collapseTimer.current);
    };
  }, []);

  // Helper to render only the 'more options' icon when collapsed
  const renderCollapsed = () => (
    <CustomControlButton
      iconName="MoreVertical"
      tooltipText="Show Controls"
      onClick={() => setCollapsed(false)}
      testId="expand_controls"
    />
  );

  return (
    <Panel
      data-testid="canvas_controls"
      className={cn(
        "react-flow__controls !left-auto !m-2 flex flex-col items-center overflow-hidden absolute w-9 min-w-9 max-w-9 rounded-md p-0 border border-border bg-background",
        collapsed
          ? "opacity-80 pt-0"
          : "opacity-100 shadow-lg pt-1"
      )}
      position="bottom-left"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <div
        style={{
          maxHeight,
          overflow: 'hidden',
          transition: 'max-height 0.4s cubic-bezier(0.4,0.2,0.2,1)',
        }}
      >
        <div ref={contentRef} className="flex flex-col justify-evenly items-center">
          {collapsed ? (
            renderCollapsed()
          ) : (
            <>
              <CustomControlButton
                iconName="ZoomIn"
                tooltipText="Zoom In"
                onClick={zoomIn}
                disabled={maxZoomReached}
                testId="zoom_in"
                backgroundClasses="h-10"
              />
              <CustomControlButton
                iconName="ZoomOut"
                tooltipText="Zoom Out"
                onClick={zoomOut}
                disabled={minZoomReached}
                testId="zoom_out"
                backgroundClasses="h-10"
              />
              <CustomControlButton
                iconName="maximize"
                tooltipText="Fit To Zoom"
                onClick={fitView}
                testId="fit_view"
                backgroundClasses="h-10"
              />
              {children}
              <CustomControlButton
                iconName={isInteractive ? "LockOpen" : "Lock"}
                tooltipText={isInteractive ? "Lock" : "Unlock"}
                onClick={onToggleInteractivity}
                backgroundClasses={
                  (isInteractive ? "" : "bg-destructive ") + "h-10"
                }
                iconClasses={
                  isInteractive ? "" : "text-primary-foreground dark:text-primary"
                }
                testId="lock_unlock"
              />
            </>
          )}
        </div>
      </div>
    </Panel>
  );
};

export default CanvasControls;
