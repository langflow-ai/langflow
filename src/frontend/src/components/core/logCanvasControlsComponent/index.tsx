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
          variant="primary"
          size="sm"
          className="flex items-center !gap-1.5"
        >
          <ForwardedIconComponent name="Terminal" className="text-primary" />
          <span className="text-mmd font-normal">Logs</span>
        </Button>
      </FlowLogsModal>
    </Panel>
  );
};

export default LogCanvasControls;
