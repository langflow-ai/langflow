import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { usePostProviderAccount } from "@/controllers/API/queries/deployment-provider-accounts/use-post-provider-account";
import { usePostDeployment } from "@/controllers/API/queries/deployments/use-post-deployment";
import useAlertStore from "@/stores/alertStore";
import {
  DeploymentStepperProvider,
  useDeploymentStepper,
} from "../contexts/deployment-stepper-context";
import DeploymentStepper from "./deployment-stepper";
import StepAttachFlows from "./step-attach-flows";
import StepDeployStatus from "./step-deploy-status";
import StepProvider from "./step-provider";
import StepReview from "./step-review";
import StepType from "./step-type";

interface DeploymentStepperModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  onTestDeployment?: (
    deployment: { id: string; name: string },
    providerId: string,
  ) => void;
  initialFlowId?: string;
  initialVersionByFlow?: Map<string, { versionId: string; versionTag: string }>;
}

export default function DeploymentStepperModal({
  open,
  setOpen,
  onTestDeployment,
  initialFlowId,
  initialVersionByFlow,
}: DeploymentStepperModalProps) {
  const [isDeploying, setIsDeploying] = useState(false);

  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!value && isDeploying) return;
        setOpen(value);
      }}
    >
      <DialogContent
        className="flex h-[85vh] w-[900px] !max-w-none flex-col gap-0 overflow-hidden border-none bg-transparent p-0 shadow-none"
        closeButtonClassName="top-5 right-4"
      >
        <DeploymentStepperProvider
          initialState={{
            initialFlowId,
            selectedVersionByFlow: initialVersionByFlow,
          }}
        >
          <DeploymentStepperModalContent
            setOpen={setOpen}
            onTestDeployment={onTestDeployment}
            onDeployingChange={setIsDeploying}
          />
        </DeploymentStepperProvider>
      </DialogContent>
    </Dialog>
  );
}

type DeploymentPhase = "idle" | "deploying" | "deployed";

function DeploymentStepperModalContent({
  setOpen,
  onTestDeployment,
  onDeployingChange,
}: {
  setOpen: (open: boolean) => void;
  onTestDeployment?: (
    deployment: { id: string; name: string },
    providerId: string,
  ) => void;
  onDeployingChange: (isDeploying: boolean) => void;
}) {
  const [deploymentPhase, setDeploymentPhase] =
    useState<DeploymentPhase>("idle");
  const [createdDeployment, setCreatedDeployment] = useState<{
    id: string;
    name: string;
  } | null>(null);

  const {
    currentStep,
    canGoNext,
    handleNext,
    handleBack,
    selectedInstance,
    setSelectedInstance,
    needsProviderAccountCreation,
    buildProviderAccountPayload,
    buildDeploymentPayload,
  } = useDeploymentStepper();

  const setErrorData = useAlertStore((state) => state.setErrorData);

  const { mutateAsync: createProviderAccount } = usePostProviderAccount();
  const { mutateAsync: createDeployment } = usePostDeployment();

  const isDeploying = deploymentPhase === "deploying";
  const isDeployed = deploymentPhase === "deployed";
  const isInDeployPhase = isDeploying || isDeployed;

  const handleDeploy = async () => {
    try {
      setDeploymentPhase("deploying");
      onDeployingChange(true);
      let providerId = selectedInstance?.id;

      if (needsProviderAccountCreation) {
        const accountPayload = buildProviderAccountPayload();
        if (!accountPayload) {
          setDeploymentPhase("idle");
          return;
        }
        const newAccount = await createProviderAccount(accountPayload);
        setSelectedInstance(newAccount);
        providerId = newAccount.id;
      }

      if (!providerId) {
        setDeploymentPhase("idle");
        return;
      }

      const payload = buildDeploymentPayload(providerId);
      const result = await createDeployment(payload);
      if (
        result &&
        typeof result === "object" &&
        "id" in result &&
        "name" in result
      ) {
        setCreatedDeployment({
          id: String(result.id),
          name: String(result.name),
        });
      }
      setDeploymentPhase("deployed");
      onDeployingChange(false);
    } catch (err: unknown) {
      setDeploymentPhase("idle");
      onDeployingChange(false);
      const message =
        err instanceof Error ? err.message : "Something went wrong";
      setErrorData({ title: "Failed to create deployment", list: [message] });
    }
  };

  const handleTest = () => {
    if (!createdDeployment || !selectedInstance?.id) return;
    onTestDeployment(createdDeployment, selectedInstance.id);
    setOpen(false);
  };

  return (
    <>
      <DialogTitle className="sr-only">Create New Deployment</DialogTitle>
      <DialogDescription className="sr-only">
        Step {currentStep} of 4
      </DialogDescription>

      {/* Title + Stepper */}
      <div className="flex flex-col gap-4 px-6 pt-6">
        <h2 className="text-center text-2xl font-semibold">
          Create New Deployment
        </h2>
        <DeploymentStepper />
      </div>

      {/* Content box: step content + footer */}
      <div className="mx-4 mb-4 mt-4 flex flex-1 flex-col overflow-hidden rounded-lg border border-border bg-background">
        <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-6 py-2">
          {isInDeployPhase ? (
            <StepDeployStatus
              phase={isDeploying ? "deploying" : "deployed"}
              deploymentName={createdDeployment?.name}
            />
          ) : (
            <>
              {currentStep === 1 && <StepProvider />}
              {currentStep === 2 && <StepType />}
              {currentStep === 3 && <StepAttachFlows />}
              {currentStep === 4 && <StepReview />}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-border px-6 py-4">
          {!isDeployed && (
            <button
              type="button"
              onClick={handleBack}
              disabled={currentStep === 1 || isDeploying}
              className="text-sm text-muted-foreground hover:text-foreground disabled:opacity-50"
            >
              Back
            </button>
          )}
          {isDeployed && <span />}
          <div className="flex items-center gap-3">
            <Button variant="outline" onClick={() => setOpen(false)}>
              {isDeployed ? "Close" : "Cancel"}
            </Button>
            {!isInDeployPhase && (
              <Button
                onClick={currentStep === 4 ? handleDeploy : handleNext}
                disabled={!canGoNext}
                data-testid="deployment-stepper-next"
              >
                {currentStep === 4 ? (
                  <>
                    <ForwardedIconComponent name="Rocket" className="h-4 w-4" />
                    Deploy
                  </>
                ) : (
                  "Next"
                )}
              </Button>
            )}
            {isDeploying && (
              <Button disabled data-testid="deployment-stepper-next">
                <ForwardedIconComponent
                  name="Rocket"
                  className="h-4 w-4 animate-pulse"
                />
                Deploying...
              </Button>
            )}
            {isDeployed && onTestDeployment && (
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
