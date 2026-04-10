import { useMemo, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { usePostProviderAccount } from "@/controllers/API/queries/deployment-provider-accounts/use-post-provider-account";
import { useGetDeployment } from "@/controllers/API/queries/deployments/use-get-deployment";
import { useGetDeploymentAttachments } from "@/controllers/API/queries/deployments/use-get-deployment-attachments";
import { usePatchDeployment } from "@/controllers/API/queries/deployments/use-patch-deployment";
import { usePostDeployment } from "@/controllers/API/queries/deployments/use-post-deployment";
import {
  DeploymentStepperProvider,
  useDeploymentStepper,
} from "../contexts/deployment-stepper-context";
import { useErrorAlert } from "../hooks/use-error-alert";
import type { Deployment, DeploymentProvider, ProviderAccount } from "../types";
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
  /** When provided, the modal opens in edit mode. */
  editingDeployment?: Deployment | null;
}

export default function DeploymentStepperModal({
  open,
  setOpen,
  onTestDeployment,
  initialFlowId,
  initialVersionByFlow,
  initialProvider,
  initialInstance,
  editingDeployment,
}: DeploymentStepperModalProps) {
  const [isDeploying, setIsDeploying] = useState(false);
  const isEditMode = !!editingDeployment;

  // Edit mode: fetch existing attachments and deployment detail for LLM.
  const { data: attachmentsData, isLoading: isLoadingAttachments } =
    useGetDeploymentAttachments(
      { deploymentId: editingDeployment?.id ?? "" },
      { enabled: open && isEditMode && !!editingDeployment?.id },
    );
  const { data: deploymentDetail, isLoading: isLoadingDetail } =
    useGetDeployment(
      { deploymentId: editingDeployment?.id ?? "" },
      { enabled: open && isEditMode && !!editingDeployment?.id },
    );

  // Build initial maps from attachments for the stepper context.
  // Tool names and connection assignments come from the provider (wxO) via
  // the /flows endpoint, NOT from the Langflow database. This means:
  //
  // - If a user renames a tool in the wxO console, the new name appears
  //   here on the next edit. Langflow doesn't cache tool names locally.
  // - If a tool is deleted in wxO, provider_data will be null and the
  //   review page falls back to the Langflow flow name.
  // - If a connection is deleted in wxO but the tool still references it,
  //   the app_id will appear in connectionsByFlow. The backend will fail
  //   fast during the update if the caller tries to attach a new tool to
  //   that stale connection.
  const editInitialState = useMemo(() => {
    if (!isEditMode || !attachmentsData?.flow_versions) return null;

    const versionMap = new Map<
      string,
      { versionId: string; versionTag: string }
    >();
    const toolNames = new Map<string, string>();
    const connectionsByFlow = new Map<string, string[]>();

    for (const fv of attachmentsData.flow_versions) {
      versionMap.set(fv.flow_id, {
        versionId: fv.id,
        versionTag: `v${fv.version_number}`,
      });
      // Pre-populate tool names from the provider (may differ from flow name).
      const providerToolName = fv.provider_data?.tool_name;
      if (providerToolName) {
        toolNames.set(fv.flow_id, providerToolName);
      }
      // Pre-populate attached connections from existing tool assignments.
      const appIds = fv.provider_data?.app_ids;
      if (appIds && appIds.length > 0) {
        connectionsByFlow.set(fv.flow_id, appIds);
      }
    }

    const llm =
      typeof deploymentDetail?.provider_data?.llm === "string"
        ? (deploymentDetail.provider_data.llm as string)
        : "";

    return { versionMap, llm, toolNames, connectionsByFlow };
  }, [isEditMode, attachmentsData, deploymentDetail]);

  const isLoadingEditData =
    isEditMode && (isLoadingAttachments || isLoadingDetail);

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
        {isLoadingEditData ? (
          <div className="flex flex-1 items-center justify-center">
            <span className="text-sm text-muted-foreground">
              Loading deployment data...
            </span>
          </div>
        ) : (
          <DeploymentStepperProvider
            key={`${open}-${editingDeployment?.id ?? ""}-${initialProvider?.id ?? ""}-${initialInstance?.id ?? ""}`}
            initialState={{
              initialFlowId,
              selectedVersionByFlow:
                initialVersionByFlow ?? editInitialState?.versionMap,
              initialProvider,
              initialInstance,
              initialStep: isEditMode
                ? 1
                : initialProvider && initialInstance
                  ? 2
                  : 1,
              editingDeployment: editingDeployment ?? undefined,
              initialLlm: editInitialState?.llm,
              initialToolNameByFlow: editInitialState?.toolNames,
              initialConnectionsByFlow: editInitialState?.connectionsByFlow,
            }}
          >
            <DeploymentStepperModalContent
              setOpen={setOpen}
              onTestDeployment={onTestDeployment}
              onDeployingChange={setIsDeploying}
            />
          </DeploymentStepperProvider>
        )}
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
    isEditMode,
    currentStep,
    totalSteps,
    minStep,
    canGoNext,
    handleNext,
    handleBack,
    selectedInstance,
    setSelectedInstance,
    needsProviderAccountCreation,
    buildProviderAccountPayload,
    buildDeploymentPayload,
    buildDeploymentUpdatePayload,
  } = useDeploymentStepper();

  const showError = useErrorAlert();

  const { mutateAsync: createProviderAccount } = usePostProviderAccount();
  const { mutateAsync: createDeployment } = usePostDeployment();
  const { mutateAsync: updateDeployment } = usePatchDeployment();

  const [isCreatingAccount, setIsCreatingAccount] = useState(false);

  const isDeploying = deploymentPhase === "deploying";
  const isDeployed = deploymentPhase === "deployed";
  const isInDeployPhase = isDeploying || isDeployed;

  // In edit mode, steps are shifted: 1=Type, 2=Attach, 3=Review.
  const logicalStep = isEditMode ? currentStep + 1 : currentStep;
  const isProviderStep = !isEditMode && currentStep === 1;
  const isFinalStep = currentStep === totalSteps;

  const handleStepNext = async () => {
    if (isProviderStep && needsProviderAccountCreation) {
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

      if (isEditMode) {
        const payload = buildDeploymentUpdatePayload();
        await updateDeployment(payload);
        onDeployingChange(false);
        setOpen(false);
        return;
      }

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
      const action = isEditMode ? "update" : "create";
      showError(`Failed to ${action} deployment`, err);
    }
  };

  const handleTest = () => {
    if (!createdDeployment || !selectedInstance?.id) return;
    onTestDeployment?.(createdDeployment, selectedInstance.id);
    setOpen(false);
  };

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

      {/* Title + Stepper */}
      <div className="flex flex-col gap-4 px-6 pt-6">
        <h2
          className="text-center text-2xl font-semibold"
          data-testid="stepper-modal-title"
        >
          {isEditMode ? "Update Deployment" : "Create New Deployment"}
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
              {logicalStep === 1 && <StepProvider />}
              {logicalStep === 2 && <StepType />}
              {logicalStep === 3 && <StepAttachFlows />}
              {logicalStep === 4 && <StepReview />}
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
