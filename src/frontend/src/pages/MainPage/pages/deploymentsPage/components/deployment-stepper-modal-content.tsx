import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { useDeploymentStepper } from "../contexts/deployment-stepper-context";
import { useDeploymentSubmit } from "../hooks/use-deployment-submit";
import DeploymentStepper from "./deployment-stepper";
import StepAttachFlows from "./step-attach-flows";
import StepDeployStatus from "./step-deploy-status";
import StepProvider from "./step-provider";
import StepReview from "./step-review";
import StepType from "./step-type";

interface DeploymentStepperModalContentProps {
  setOpen: (open: boolean) => void;
  onTestDeployment?: (
    deployment: { id: string; name: string },
    providerId: string,
  ) => void;
  onDeployingChange: (isDeploying: boolean) => void;
}

export default function DeploymentStepperModalContent({
  setOpen,
  onTestDeployment,
  onDeployingChange,
}: DeploymentStepperModalContentProps) {
  const {
    isEditMode,
    currentStep,
    totalSteps,
    minStep,
    canGoNext,
    handleBack,
  } = useDeploymentStepper();

  const {
    deploymentPhase,
    createdDeployment,
    isCreatingAccount,
    isDeploying,
    isDeployed,
    isInDeployPhase,
    isFinalStep,
    handleStepNext,
    handleDeploy,
    handleTest,
  } = useDeploymentSubmit({
    setOpen,
    onTestDeployment,
    onDeployingChange,
  });

  const logicalStep = isEditMode ? currentStep + 1 : currentStep;
  const actionLabel = isEditMode ? "Update" : "Deploy";
  const actionIcon = isEditMode ? "Save" : "Rocket";
  const progressLabel = isEditMode ? "Updating..." : "Deploying...";

  return (
    <>
      <DialogTitle className="sr-only">
        {isEditMode ? "Update Deployment" : "Create New Deployment"}
      </DialogTitle>
      <DialogDescription className="sr-only">
        Step {currentStep} of {totalSteps}
      </DialogDescription>

      <div className="flex flex-col gap-4 px-6 pt-6">
        <h2
          className="text-center text-2xl font-semibold"
          data-testid="stepper-modal-title"
        >
          {isEditMode ? "Update Deployment" : "Create New Deployment"}
        </h2>
        <DeploymentStepper />
      </div>

      <div className="mx-4 mb-4 mt-4 flex flex-1 flex-col overflow-hidden rounded-lg border border-border bg-background">
        <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-6 py-2">
          {isInDeployPhase ? (
            <StepDeployStatus
              phase={deploymentPhase === "deploying" ? "deploying" : "deployed"}
              deploymentName={createdDeployment?.name}
            />
          ) : (
            <>
              {logicalStep === 1 && <StepProvider />}
              {logicalStep === 2 && <StepType />}
              {logicalStep === 3 && <StepAttachFlows />}
              {logicalStep === 4 && <StepReview />}
            </>
          )}
        </div>

        <div className="flex items-center justify-between border-t border-border px-6 py-4">
          <Button variant="ghost" onClick={() => setOpen(false)}>
            {isDeployed ? "Close" : "Cancel"}
          </Button>
          <div className="flex items-center gap-3">
            {!isDeployed && (
              <Button
                variant="outline"
                onClick={handleBack}
                disabled={currentStep === minStep || isDeploying}
              >
                Back
              </Button>
            )}
            {!isInDeployPhase && (
              <Button
                onClick={isFinalStep ? handleDeploy : handleStepNext}
                disabled={!canGoNext || isCreatingAccount}
                data-testid="deployment-stepper-next"
              >
                {isFinalStep ? (
                  <>
                    <ForwardedIconComponent
                      name={actionIcon}
                      className="h-4 w-4"
                    />
                    {actionLabel}
                  </>
                ) : isCreatingAccount ? (
                  "Connecting..."
                ) : (
                  "Next"
                )}
              </Button>
            )}
            {isDeploying && (
              <Button disabled data-testid="deployment-stepper-next">
                <ForwardedIconComponent
                  name={actionIcon}
                  className="h-4 w-4 animate-pulse"
                />
                {progressLabel}
              </Button>
            )}
            {isDeployed && onTestDeployment && !isEditMode && (
              <Button
                data-testid="deployment-stepper-test"
                onClick={handleTest}
              >
                Test
              </Button>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
