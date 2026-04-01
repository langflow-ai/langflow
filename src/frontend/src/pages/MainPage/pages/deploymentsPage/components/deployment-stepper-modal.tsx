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
import { useGetDeploymentAttachments } from "@/controllers/API/queries/deployments/use-get-deployment-attachments";
import { usePatchDeployment } from "@/controllers/API/queries/deployments/use-patch-deployment";
import { usePatchDeploymentSnapshot } from "@/controllers/API/queries/deployments/use-patch-deployment-snapshot";
import { usePostDeployment } from "@/controllers/API/queries/deployments/use-post-deployment";
import useAlertStore from "@/stores/alertStore";
import type { Deployment, ProviderAccount } from "../types";
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
  /** When provided, the modal opens in edit mode. */
  editingDeployment?: Deployment | null;
  /** The provider account for the deployment being edited. */
  editingProviderAccount?: ProviderAccount | null;
}

export default function DeploymentStepperModal({
  open,
  setOpen,
  onTestDeployment,
  initialFlowId,
  initialVersionByFlow,
  editingDeployment,
  editingProviderAccount,
}: DeploymentStepperModalProps) {
  const [isDeploying, setIsDeploying] = useState(false);
  const isEditMode = !!editingDeployment;

  // Fetch existing attachments when editing so the stepper can show them
  const { data: attachmentsData, isLoading: isLoadingAttachments } =
    useGetDeploymentAttachments(
      { deploymentId: editingDeployment?.id ?? "" },
      { enabled: open && isEditMode && !!editingDeployment?.id },
    );

  // Build the selectedVersionByFlow and attachedConnectionByFlow maps from
  // existing attachments so the Attach Flows step shows current state.
  const {
    editVersionByFlow,
    editAttachedConnectionByFlow,
    editSnapshotByFlow,
  } = useMemo(() => {
    if (!isEditMode || !attachmentsData?.attachments?.length) {
      return {
        editVersionByFlow: undefined,
        editAttachedConnectionByFlow: undefined,
        editSnapshotByFlow: undefined,
      };
    }
    const versionMap = new Map<
      string,
      { versionId: string; versionTag: string }
    >();
    const connectionMap = new Map<string, string[]>();
    const snapshotMap = new Map<string, string>();

    for (const att of attachmentsData.attachments) {
      versionMap.set(att.flow_id, {
        versionId: att.flow_version_id,
        versionTag: att.version_tag,
      });
      if (att.provider_snapshot_id) {
        snapshotMap.set(att.flow_id, att.provider_snapshot_id);
      }
      // Use the real connection_ids from the provider if available,
      // otherwise fall back to provider_snapshot_id so the flow shows
      // as ATTACHED in the list panel.
      const connIds =
        att.connection_ids.length > 0
          ? att.connection_ids
          : att.provider_snapshot_id
            ? [att.provider_snapshot_id]
            : [att.flow_version_id];
      connectionMap.set(att.flow_id, connIds);
    }

    return {
      editVersionByFlow: versionMap,
      editAttachedConnectionByFlow: connectionMap,
      editSnapshotByFlow: snapshotMap,
    };
  }, [isEditMode, attachmentsData]);

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
        {/* In edit mode, wait for attachments to load before mounting the provider
            so the initial state includes existing flow versions. */}
        {isEditMode && isLoadingAttachments ? (
          <div className="flex flex-1 items-center justify-center">
            <span className="text-sm text-muted-foreground">
              Loading deployment data...
            </span>
          </div>
        ) : (
          <DeploymentStepperProvider
            initialState={{
              initialFlowId,
              selectedVersionByFlow: initialVersionByFlow ?? editVersionByFlow,
              editingDeployment: editingDeployment ?? undefined,
              editingProviderAccount: editingProviderAccount ?? undefined,
              initialAttachedConnectionByFlow: editAttachedConnectionByFlow,
              initialSnapshotByFlow: editSnapshotByFlow,
              initialLlmFromProvider: attachmentsData?.llm ?? undefined,
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
    editingDeployment,
    currentStep,
    totalSteps,
    canGoNext,
    handleNext,
    handleBack,
    selectedInstance,
    setSelectedInstance,
    needsProviderAccountCreation,
    buildProviderAccountPayload,
    buildDeploymentPayload,
    buildDeploymentUpdatePayload,
    getSnapshotUpdates,
  } = useDeploymentStepper();

  const setErrorData = useAlertStore((state) => state.setErrorData);

  const { mutateAsync: createProviderAccount } = usePostProviderAccount();
  const { mutateAsync: createDeployment } = usePostDeployment();
  const { mutateAsync: updateDeployment } = usePatchDeployment();
  const { mutateAsync: updateSnapshot } = usePatchDeploymentSnapshot();

  const [isCreatingAccount, setIsCreatingAccount] = useState(false);

  const isDeploying = deploymentPhase === "deploying";
  const isDeployed = deploymentPhase === "deployed";
  const isInDeployPhase = isDeploying || isDeployed;

  // In edit mode, the logical step for content is shifted
  // Create mode: step 1=Provider, 2=Type, 3=AttachFlows, 4=Review
  // Edit mode:   step 1=Type, 2=AttachFlows, 3=Review
  const logicalStep = isEditMode ? currentStep + 1 : currentStep;

  // The provider step (step 1 create mode) needs account creation
  const isProviderStep = !isEditMode && currentStep === 1;

  const handleStepNext = async () => {
    if (isProviderStep && needsProviderAccountCreation) {
      const accountPayload = buildProviderAccountPayload();
      if (!accountPayload) return;
      try {
        setIsCreatingAccount(true);
        const newAccount = await createProviderAccount(accountPayload);
        setSelectedInstance(newAccount);
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Something went wrong";
        setErrorData({
          title: "Failed to create provider account",
          list: [message],
        });
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
        // First, update any existing tools whose version changed (in-place).
        const snapshotUpdates = getSnapshotUpdates();
        for (const snap of snapshotUpdates) {
          await updateSnapshot(snap);
        }

        // Then, update the deployment itself (new binds, removals, LLM, description)
        const payload = buildDeploymentUpdatePayload();
        await updateDeployment(payload);

        // Auto-close on successful edit — no success screen needed.
        onDeployingChange(false);
        setOpen(false);
        return;
      } else {
        // Create new deployment
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
      }

      setDeploymentPhase("deployed");
      onDeployingChange(false);
    } catch (err: unknown) {
      setDeploymentPhase("idle");
      onDeployingChange(false);
      const message =
        err instanceof Error ? err.message : "Something went wrong";
      const action = isEditMode ? "update" : "create";
      setErrorData({
        title: `Failed to ${action} deployment`,
        list: [message],
      });
    }
  };

  const handleTest = () => {
    if (!createdDeployment || !selectedInstance?.id) return;
    onTestDeployment?.(createdDeployment, selectedInstance.id);
    setOpen(false);
  };

  const isFinalStep = currentStep === totalSteps;
  const actionLabel = isEditMode ? "Update" : "Deploy";
  const actionIcon = isEditMode ? "Save" : "Rocket";
  const progressLabel = isEditMode ? "Updating..." : "Deploying...";
  const successLabel = isEditMode
    ? "Update successful"
    : "Deployment successful";
  const successDescription = isEditMode
    ? createdDeployment
      ? `"${createdDeployment.name}" has been updated.`
      : "Your deployment has been updated."
    : createdDeployment
      ? `"${createdDeployment.name}" is live and ready to use.`
      : "Your deployment is live and ready to use.";

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
        <h2 className="text-center text-2xl font-semibold">
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
              isEditMode={isEditMode}
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
            {isDeployed && isEditMode && (
              <Button
                data-testid="deployment-stepper-done"
                onClick={() => setOpen(false)}
              >
                Done
              </Button>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
