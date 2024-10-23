import { 
  ControlButton, 
  Panel, 
  useReactFlow, 
  useStore, 
  useStoreApi, 
  type ReactFlowState 
} from "reactflow"
import { shallow } from 'zustand/shallow';
import IconComponent from "@/components/genericIconComponent";
import ShadTooltip from "@/components/shadTooltipComponent";
import { cn } from "@/utils/utils";

type CustomControlButtonProps = {
  iconName: string;
  tooltipText: string;
  onClick: () => void;
  disabled?: boolean;
  backgroundClasses?: string
  iconClasses?: string
  testId?: string;
};

export const CustomControlButton = (
  {iconName, tooltipText, onClick, disabled, backgroundClasses, iconClasses, testId}: CustomControlButtonProps
): JSX.Element => {
  return (
    <ControlButton
      data-testid={testId}
      className="!w-8 !h-8 !p-0 rounded"
      onClick={onClick}
      disabled={disabled}
    >
      <ShadTooltip content={tooltipText}>
        <div className={cn("p-2.5 rounded", backgroundClasses)}>
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

const CanvasControls = ({ children}) => {
  const store = useStoreApi();
  const { fitView, zoomIn, zoomOut } = useReactFlow();
  const { isInteractive, minZoomReached, maxZoomReached } = useStore(selector, shallow);

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
      className="react-flow__controls flex gap-1.5 fill-foreground stroke-foreground text-primary rounded border-secondary-hover bg-background border p-1.5 [&>button]:border-0 [&>button]:bg-background hover:[&>button]:bg-accent"
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
        testId="fit_to_zoom"
      />
      {/* Lock/Unlock */}
      <CustomControlButton
        iconName={isInteractive ? "LockOpen" : "Lock"}
        tooltipText={isInteractive ? "Lock" : "Unlock"}
        onClick={onToggleInteractivity}
        backgroundClasses={isInteractive ? "" : "bg-destructive"}
        iconClasses={isInteractive ? "" : "text-primary"}
        testId="lock_unlock"
      />
      {children}
    </Panel>
  )
}

export default CanvasControls;
