import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import CreateEvaluationModal from "@/modals/createEvaluationModal";
import useFlowStore from "@/stores/flowStore";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";

const EvaluateIcon = () => (
  <ForwardedIconComponent
    name="FlaskConical"
    className="h-4 w-4 transition-all"
    strokeWidth={2}
  />
);

const ButtonLabel = () => (
  <span className="hidden md:block">Evaluate</span>
);

const EvaluateButton = () => {
  const [open, setOpen] = useState(false);
  const navigate = useCustomNavigate();
  const currentFlow = useFlowStore((state) => state.currentFlow);
  const hasIO = useFlowStore((state) => state.hasIO);

  const handleSuccess = (evaluationId: string) => {
    // Navigate to evaluation results
    navigate(`/evaluations/${evaluationId}`);
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
