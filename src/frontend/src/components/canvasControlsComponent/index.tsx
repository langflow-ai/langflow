import IconComponent from "@/components/genericIconComponent";
import ShadTooltip from "@/components/shadTooltipComponent";
import { cn } from "@/utils/utils";
import {
  ControlButton,
  Panel,
  useReactFlow,
  useStore,
  useStoreApi,
  type ReactFlowState,
} from "reactflow";
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
      className="!h-8 !w-8 rounded !p-0"
      onClick={onClick}
      disabled={disabled}
      title={testId?.replace(/_/g, " ")}
    >
      <ShadTooltip content={tooltipText}>
        <div className={cn("rounded p-2.5", backgroundClasses)}>
          <IconComponent
            name={iconName}
            aria-hidden="true"
            className={cn("scale-150 text-muted-foreground", iconClasses)}
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

  const onToggleInteractivity = () => {
    store.setState({
      nodesDraggable: !isInteractive,
      nodesConnectable: !isInteractive,
      elementsSelectable: !isInteractive,
    });
  };

  return (
    <Panel
      data-testid="canvas_controls"
      className="react-flow__controls !m-2 flex gap-1.5 rounded-md border border-secondary-hover bg-background fill-foreground stroke-foreground p-1.5 text-primary shadow [&>button]:border-0 [&>button]:bg-background hover:[&>button]:bg-accent"
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
      {children}
    </Panel>
  );
};

export default CanvasControls;
