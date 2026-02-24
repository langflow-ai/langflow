import { Panel } from "@xyflow/react";
import { useParams } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";

const LogCanvasControls = () => {
  const { id } = useParams();
  const navigate = useCustomNavigate();

  return (
    <Panel
      data-testid="canvas_controls"
      className="react-flow__controls !m-2 rounded-md"
      position="bottom-left"
    >
      <Button
        variant="primary"
        size="sm"
        className="flex items-center !gap-1.5"
        onClick={() => {
          if (!id) return;
          navigate(`/flow/${id}/insights`);
        }}
      >
        <ForwardedIconComponent name="Terminal" className="text-primary" />
        <span className="text-mmd font-normal">Logs</span>
      </Button>
    </Panel>
  );
};

export default LogCanvasControls;
