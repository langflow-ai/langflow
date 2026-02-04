import { Panel } from "@xyflow/react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useSidebar } from "@/components/ui/sidebar";

const LogCanvasControls = () => {
  const { setActiveSection, open, toggleSidebar } = useSidebar();

  const handleOpenLogs = () => {
    setActiveSection("logs");
    if (!open) {
      toggleSidebar();
    }
  };

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
        onClick={handleOpenLogs}
      >
        <ForwardedIconComponent name="Terminal" className="text-primary" />
        <span className="text-mmd font-normal">Logs</span>
      </Button>
    </Panel>
  );
};

export default LogCanvasControls;
