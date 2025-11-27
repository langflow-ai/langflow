import { Panel } from "@xyflow/react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import FlowLogsModal from "@/modals/flowLogsModal";

const LogCanvasControls = () => {
  return (
    <Panel
      data-testid="canvas_controls"
      className="react-flow__controls !m-2 rounded-md"
      position="bottom-left"
    >
      <FlowLogsModal>
        <Button
          variant="link"
          size="sm"
          className="bg-background-surface text-secondary-font flex items-center !gap-1.5 border border-primary-border"
        >
          <ForwardedIconComponent
            name="Terminal"
            className="text-secondary-font"
          />
          <span>Logs</span>
        </Button>
      </FlowLogsModal>
    </Panel>
  );
};

export default LogCanvasControls;
