import { ControlButton, Panel, useViewport, useReactFlow } from "reactflow"
import IconComponent from "@/components/genericIconComponent";
import ShadTooltip from "@/components/shadTooltipComponent";

const CanvasControls = ({ children}) => {
  const { zoomIn, zoomOut } = useReactFlow();
  const { zoom } = useViewport();

  const zoomPercentage = (zoom * 100).toFixed(0);

  return (
    <Panel
      className="react-flow__controls flex fill-foreground stroke-foreground text-primary [&>button]:border-b-border [&>button]:bg-muted hover:[&>button]:bg-border"
      position="bottom-left"
    >
      <ControlButton
        data-testid="add_note"
        onClick={() => {
          zoomIn();
        }}
      >
        <ShadTooltip content="Zoom In">
          <div>
            <IconComponent
              name="ZoomIn"
              aria-hidden="true"
              className="scale-125"
            />
            </div>
        </ShadTooltip>
      </ControlButton>
      <span>
        {`${zoomPercentage}%`}
      </span>
      <ControlButton
        data-testid="add_note"
        onClick={() => {
          zoomOut();
        }}
      >
        <ShadTooltip content="Zoom Out">
          <div>
            <IconComponent
              name="ZoomOut"
              aria-hidden="true"
              className="scale-125"
            />
            </div>
        </ShadTooltip>
      </ControlButton>
      {children}
    </Panel>
  )
}

export default CanvasControls;
