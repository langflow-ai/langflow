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
import { useCallback, useEffect } from "react";
import { useShallow } from "zustand/react/shallow";
import { shallow } from "zustand/shallow";

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

  useEffect(() => {
    store.setState({
      nodesDraggable: !isLocked,
      nodesConnectable: !isLocked,
      elementsSelectable: !isLocked,
    });
  }, [isLocked]);

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

  return (
    <Panel
      data-testid="canvas_controls"
      className="react-flow__controls !left-auto !m-2 flex !flex-col gap-1.5 rounded-md border border-border bg-background fill-foreground stroke-foreground p-0.5 text-primary [&>button]:border-0 [&>button]:bg-background hover:[&>button]:bg-accent"
      position="bottom-left"
    >
      {/* Zoom In */}
      <CustomControlButton
        iconName="ZoomIn"
        tooltipText="Zoom In"
        onClick={zoomIn}
        disabled={maxZoomReached}
        testId="zoom_in"
      />
      {/* Zoom Out */}
      <CustomControlButton
        iconName="ZoomOut"
        tooltipText="Zoom Out"
        onClick={zoomOut}
        disabled={minZoomReached}
        testId="zoom_out"
      />
      {/* Zoom To Fit */}
      <CustomControlButton
        iconName="maximize"
        tooltipText="Fit To Zoom"
        onClick={fitView}
        testId="fit_view"
      />
      {children}
      {/* Lock/Unlock */}
      <CustomControlButton
        iconName={isInteractive ? "LockOpen" : "Lock"}
        tooltipText={isInteractive ? "Lock" : "Unlock"}
        onClick={onToggleInteractivity}
        backgroundClasses={isInteractive ? "" : "bg-destructive"}
        iconClasses={
          isInteractive ? "" : "text-primary-foreground dark:text-primary"
        }
        testId="lock_unlock"
      />
    </Panel>
  );
};

export default CanvasControls;
