import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { useSidebar } from "@/components/ui/sidebar";
import CreateEvaluationModal from "@/modals/createEvaluationModal";
import useFlowStore from "@/stores/flowStore";

const EvaluateIcon = () => (
  <ForwardedIconComponent
    name="FlaskConical"
    className="h-4 w-4 transition-all"
    strokeWidth={2}
  />
);

const ButtonLabel = () => <span className="hidden md:block">Evaluate</span>;

const EvaluateButton = () => {
  const [open, setOpen] = useState(false);
  const { setActiveSection, setOpen: setSidebarOpen } = useSidebar();
  const currentFlow = useFlowStore((state) => state.currentFlow);
  const hasIO = useFlowStore((state) => state.hasIO);

  const handleSuccess = (_evaluationId: string) => {
    // Switch to evaluations section in sidebar instead of navigating away
    // The EvaluationsSidebarGroup will auto-select the first (newest) evaluation
    setActiveSection("evaluations");
    setSidebarOpen(true);
  };

  const isEnabled = hasIO && currentFlow?.id;

  return (
    <>
      {isEnabled ? (
        <button
          onClick={() => setOpen(true)}
          data-testid="evaluate-btn-flow-toolbar"
          className="playground-btn-flow-toolbar hover:bg-accent"
        >
          <EvaluateIcon />
          <ButtonLabel />
        </button>
      ) : (
        <ShadTooltip content="Add a Chat Input or Chat Output to use evaluations">
          <div
            className="playground-btn-flow-toolbar cursor-not-allowed text-muted-foreground duration-150"
            data-testid="evaluate-btn-flow-disabled"
          >
            <EvaluateIcon />
            <ButtonLabel />
          </div>
        </ShadTooltip>
      )}

      {currentFlow && (
        <CreateEvaluationModal
          open={open}
          setOpen={setOpen}
          flowId={currentFlow.id}
          flowName={currentFlow.name}
          onSuccess={handleSuccess}
        />
      )}
    </>
  );
};

export default EvaluateButton;
