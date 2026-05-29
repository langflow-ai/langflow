import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
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
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import { useFolderStore } from "@/stores/foldersStore";
import {
  DeploymentStepperProvider,
  useDeploymentStepper,
} from "../contexts/deployment-stepper-context";
import { isDeploymentUpdatePayloadEmpty } from "../helpers/deployment-payload-builders";
import { useErrorAlert } from "../hooks/use-error-alert";
import {
  DEFAULT_FLOW_NAME,
  type Deployment,
  type DeploymentProvider,
  getDeploymentDisplayName,
  getSelectedFlowVersionKey,
  type ProviderAccount,
  type SelectedFlowVersion,
} from "../types";
import DeploymentStepper, { CREATE_DEPLOYED_STEPS } from "./deployment-stepper";
import DeploymentStepperFooter from "./deployment-stepper-footer";
import DeploymentSuccessContent from "./deployment-success-content";
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
  initialVersionByFlow?: Map<string, SelectedFlowVersion>;
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
  const { t } = useTranslation();
  const [isDeploying, setIsDeploying] = useState(false);
  const isEditMode = !!editingDeployment;
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const currentFlowProjectId = useFlowStore(
    (state) => state.currentFlow?.folder_id,
  );
  const resolvedProjectId =
    currentFlowProjectId ?? folderId ?? myCollectionId ?? undefined;

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

    const versionMap = new Map<string, SelectedFlowVersion>();
    const toolNames = new Map<string, string>();
    const connectionsByFlow = new Map<string, string[]>();

    for (const fv of attachmentsData.flow_versions) {
      const key = getSelectedFlowVersionKey(fv.flow_id, fv.id);
      versionMap.set(key, {
        key,
        flowId: fv.flow_id,
        flowName: fv.flow_name ?? DEFAULT_FLOW_NAME,
        versionId: fv.id,
        versionTag: `v${fv.version_number}`,
      });
      // Pre-populate tool names from the provider (may differ from flow name).
      const providerToolName = fv.provider_data?.tool_display_name;
      if (providerToolName) {
        toolNames.set(key, providerToolName);
      }
      // Pre-populate attached connections from existing tool assignments.
      const appIds = fv.provider_data?.app_ids;
      if (appIds && appIds.length > 0) {
        connectionsByFlow.set(key, appIds);
      }
    }

    const llm =
      typeof deploymentDetail?.provider_data?.llm === "string"
        ? deploymentDetail.provider_data.llm
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
        hideCloseButton
        overlayClassName="bg-black/30 dark:bg-black/50 backdrop-blur"
      >
        <DeploymentStepperProvider
          key={`${open}-${editingDeployment?.id ?? ""}-${initialProvider?.id ?? ""}-${initialInstance?.id ?? ""}-${isLoadingEditData}`}
          initialState={{
            projectId: resolvedProjectId,
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
          {isLoadingEditData ? (
            <div className="flex flex-1 items-center justify-center">
              <span className="text-sm text-muted-foreground">
                {t("deployments.loadingDeploymentData")}
              </span>
            </div>
          ) : (
            <DeploymentStepperModalContent
              setOpen={setOpen}
              onTestDeployment={onTestDeployment}
              onDeployingChange={setIsDeploying}
            />
          )}
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
    isEditMode,
    currentStep,
    totalSteps,
    minStep,
    canGoNext,
    handleNext,
    handleBack,
    selectedProvider,
    selectedInstance,
    setSelectedInstance,
    needsProviderAccountCreation,
    buildProviderAccountPayload,
    buildDeploymentPayload,
    buildDeploymentUpdatePayload,
  } = useDeploymentStepper();

  const { t } = useTranslation();
  const showError = useErrorAlert();
  const setNoticeData = useAlertStore((state) => state.setNoticeData);

  const { mutateAsync: createProviderAccount } = usePostProviderAccount();
  const { mutateAsync: createDeployment } = usePostDeployment();
  const { mutateAsync: updateDeployment } = usePatchDeployment();

  const [isCreatingAccount, setIsCreatingAccount] = useState(false);

  const isDeploying = deploymentPhase === "deploying";
  const isDeployed = deploymentPhase === "deployed";
  const isInDeployPhase = isDeploying || isDeployed;
  const providerConsoleUrl = "https://www.ibm.com/products/watsonx-orchestrate";
  const providerDisplayName = selectedProvider?.name ?? "watsonx Orchestrate";

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
        showError(t("deployments.failedToCreateProviderAccount"), err);
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
        if (isDeploymentUpdatePayloadEmpty(payload)) {
          onDeployingChange(false);
          setDeploymentPhase("idle");
          setNoticeData({ title: t("deployments.noChangesToSave") });
          return;
        }
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
      if (result && typeof result === "object" && "id" in result) {
        const deployment = result as Deployment;
        setCreatedDeployment({
          id: String(result.id),
          name: getDeploymentDisplayName(deployment),
        });
      }
      setDeploymentPhase("deployed");
      onDeployingChange(false);
    } catch (err: unknown) {
      setDeploymentPhase("idle");
      onDeployingChange(false);
      showError(
        isEditMode
          ? t("deployments.failedToUpdateDeployment")
          : t("deployments.failedToCreateDeployment"),
        err,
      );
    }
  };

  const handleTest = () => {
    if (!createdDeployment || !selectedInstance?.id) return;
    onTestDeployment?.(createdDeployment, selectedInstance.id);
    setOpen(false);
  };

  const actionLabel = isEditMode
    ? t("deployments.update")
    : t("deployments.deploy");
  const actionIcon = isEditMode ? "Save" : "Rocket";
  const progressLabel = isEditMode
    ? t("deployments.updating")
    : t("deployments.deploying");

  return (
    <>
      <DialogTitle className="sr-only">
        {isEditMode
          ? t("deployments.updateDeployment")
          : t("deployments.createNewDeploymentTitle")}
      </DialogTitle>
      <DialogDescription className="sr-only">
        {t("deployments.stepOf", { current: currentStep, total: totalSteps })}
      </DialogDescription>

      {/* Title + Stepper */}
      <div className="flex flex-col gap-4 px-6 pt-6">
        <h2
          className="text-center text-2xl font-semibold"
          data-testid="stepper-modal-title"
        >
          {isDeployed && !isEditMode
            ? t("deployments.deployed")
            : isEditMode
              ? t("deployments.updateDeployment")
              : t("deployments.createNewDeploymentTitle")}
        </h2>
        <DeploymentStepper
          steps={!isEditMode && isDeployed ? CREATE_DEPLOYED_STEPS : undefined}
          currentStepOverride={!isEditMode && isDeployed ? 4 : undefined}
        />
      </div>

      {/* Content box: step content + footer */}
      <div className="mx-4 mb-4 mt-4 flex flex-1 flex-col overflow-hidden rounded-lg border border-border bg-background">
        <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-6 py-2">
          {isInDeployPhase ? (
            isDeployed && !isEditMode ? (
              <DeploymentSuccessContent
                deploymentName={createdDeployment?.name}
                providerName={providerDisplayName}
                providerUrl={providerConsoleUrl}
                showTestButton={
                  !!onTestDeployment &&
                  !!createdDeployment &&
                  !!selectedInstance?.id
                }
                onTest={handleTest}
              />
            ) : (
              <StepDeployStatus
                phase={isDeploying ? "deploying" : "deployed"}
                deploymentName={createdDeployment?.name}
              />
            )
          ) : (
            <>
              {logicalStep === 1 && <StepProvider />}
              {logicalStep === 2 && <StepType />}
              {logicalStep === 3 && <StepAttachFlows />}
              {logicalStep === 4 && <StepReview />}
            </>
          )}
        </div>

        <DeploymentStepperFooter
          canGoNext={canGoNext}
          currentStep={currentStep}
          isCreatingAccount={isCreatingAccount}
          isDeployed={isDeployed}
          isDeploying={isDeploying}
          isInDeployPhase={isInDeployPhase}
          isFinalStep={isFinalStep}
          minStep={minStep}
          actionIcon={actionIcon}
          actionLabel={actionLabel}
          progressLabel={progressLabel}
          onBack={handleBack}
          onCancel={() => setOpen(false)}
          onClose={() => setOpen(false)}
          onPrimaryAction={isFinalStep ? handleDeploy : handleStepNext}
        />
      </div>
    </>
  );
}
