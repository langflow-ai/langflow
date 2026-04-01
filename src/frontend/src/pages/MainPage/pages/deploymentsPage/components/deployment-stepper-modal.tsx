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
import {
  DeploymentStepperProvider,
  useDeploymentStepper,
} from "../contexts/deployment-stepper-context";
import { useErrorAlert } from "../hooks/use-error-alert";
import type { DeploymentProvider, ProviderAccount } from "../types";
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
  initialProvider?: DeploymentProvider;
  initialInstance?: ProviderAccount;
}

export default function DeploymentStepperModal({
  open,
  setOpen,
  onTestDeployment,
  initialFlowId,
  initialVersionByFlow,
  initialProvider,
  initialInstance,
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
          key={`${open}-${initialProvider?.id ?? ""}-${initialInstance?.id ?? ""}`}
          initialState={{
            initialFlowId,
            selectedVersionByFlow: initialVersionByFlow,
            initialProvider,
            initialInstance,
            initialStep: initialProvider && initialInstance ? 2 : 1,
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
    minStep,
    canGoNext,
    handleNext,
    handleBack,
    selectedInstance,
    setSelectedInstance,
    needsProviderAccountCreation,
    buildProviderAccountPayload,
    buildDeploymentPayload,
  } = useDeploymentStepper();

  const showError = useErrorAlert();

  const { mutateAsync: createProviderAccount } = usePostProviderAccount();
  const { mutateAsync: createDeployment } = usePostDeployment();

  const [isCreatingAccount, setIsCreatingAccount] = useState(false);

  const isDeploying = deploymentPhase === "deploying";
  const isDeployed = deploymentPhase === "deployed";
  const isInDeployPhase = isDeploying || isDeployed;

  const handleStepNext = async () => {
    if (currentStep === 1 && needsProviderAccountCreation) {
      const accountPayload = buildProviderAccountPayload();
      if (!accountPayload) return;
      try {
        setIsCreatingAccount(true);
        const newAccount = await createProviderAccount(accountPayload);
        setSelectedInstance(newAccount);
      } catch (err: unknown) {
        showError("Failed to create provider account", err);
        return;
      } finally {
        setIsCreatingAccount(false);
      }
    }
    handleNext();
  };

  const handleDeploy = async () => {
    try {
      setDeploymentPhase("deploying");
      onDeployingChange(true);
      const providerId = selectedInstance?.id;

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
      showError("Failed to create deployment", err);
    }
  };

  const handleTest = () => {
    if (!createdDeployment || !selectedInstance?.id) return;
    onTestDeployment?.(createdDeployment, selectedInstance.id);
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
                onClick={currentStep === 4 ? handleDeploy : handleStepNext}
                disabled={!canGoNext || isCreatingAccount}
                data-testid="deployment-stepper-next"
              >
                {currentStep === 4 ? (
                  <>
                    <ForwardedIconComponent name="Rocket" className="h-4 w-4" />
                    Deploy
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
