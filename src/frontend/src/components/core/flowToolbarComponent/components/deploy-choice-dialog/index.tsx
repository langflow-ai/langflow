import { Dialog, DialogContent } from "@/components/ui/dialog";
import type {
  DeploymentProvider,
  ProviderAccount,
} from "@/pages/MainPage/pages/deploymentsPage/types";
import DeploymentPhaseContent from "./deployment-phase";
import ProviderPhaseContent from "./provider-phase";
import ReviewPhaseContent from "./review-phase";
import UpdatePhaseContent from "./update-phase";
import { useDeployChoiceDialogState } from "./use-deploy-choice-dialog-state";

interface DeployChoiceDialogProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  providers: ProviderAccount[];
  flowId: string;
  snapshotVersionId: string;
  snapshotVersionTag: string;
  onChooseNew: (preselected?: {
    provider: DeploymentProvider;
    instance: ProviderAccount;
  }) => void;
  onUpdateComplete: (deploymentName: string) => void;
  onTestDeployment?: (
    deployment: { id: string; name: string },
    providerId: string,
  ) => void;
}

export default function DeployChoiceDialog({
  open,
  setOpen,
  providers,
  flowId,
  snapshotVersionId,
  snapshotVersionTag,
  onChooseNew,
  onUpdateComplete,
  onTestDeployment,
}: DeployChoiceDialogProps) {
  const {
    phase,
    selectedProviderId,
    setSelectedProviderId,
    selectedProvider,
    deployments,
    selectedDeployment,
    setSelectedDeployment,
    reviewAttachments,
    reviewAttachment,
    handleSelectAttachment,
    handleProviderContinue,
    handleDeploymentContinue,
    handleReviewConfirm,
    handleBack,
    isLoadingDeployments,
    isLoadingReviewAttachment,
    isBusy,
    isUpdating,
    isUpdated,
    isInUpdatePhase,
    updatedDeploymentName,
    updatedDeploymentId,
  } = useDeployChoiceDialogState({
    open,
    providers,
    flowId,
    snapshotVersionId,
    onChooseNew,
  });

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (isBusy) return;
        if (isUpdated) {
          onUpdateComplete(updatedDeploymentName);
          return;
        }
        setOpen(nextOpen);
      }}
    >
      <DialogContent className="max-h-screen w-full max-w-xl overflow-y-auto">
        {isInUpdatePhase ? (
          <UpdatePhaseContent
            isUpdating={isUpdating}
            isUpdated={isUpdated}
            deploymentName={updatedDeploymentName}
            onClose={() => onUpdateComplete(updatedDeploymentName)}
            onTest={
              onTestDeployment && updatedDeploymentId && selectedProviderId
                ? () =>
                    onTestDeployment(
                      { id: updatedDeploymentId, name: updatedDeploymentName },
                      selectedProviderId,
                    )
                : undefined
            }
          />
        ) : phase === "provider" ? (
          <ProviderPhaseContent
            providers={providers}
            selectedProviderId={selectedProviderId}
            onSelectProvider={setSelectedProviderId}
            onContinue={handleProviderContinue}
            onCancel={() => setOpen(false)}
          />
        ) : phase === "review" ? (
          <ReviewPhaseContent
            attachments={reviewAttachments}
            attachment={reviewAttachment}
            loading={isLoadingReviewAttachment}
            onSelectAttachment={handleSelectAttachment}
            newVersionTag={snapshotVersionTag}
            isBusy={isBusy}
            onBack={handleBack}
            onConfirm={handleReviewConfirm}
            onCancel={() => setOpen(false)}
          />
        ) : (
          <DeploymentPhaseContent
            selectedProvider={selectedProvider}
            deployments={deployments}
            selectedDeployment={selectedDeployment}
            onSelectDeployment={setSelectedDeployment}
            isLoading={isLoadingDeployments}
            isBusy={isBusy}
            showBack={providers.length > 1}
            onBack={handleBack}
            onContinue={handleDeploymentContinue}
            onCancel={() => setOpen(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
