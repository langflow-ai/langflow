import { useCallback, useEffect, useMemo, useState } from "react";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { usePatchSnapshot } from "@/controllers/API/queries/deployments";
import { useGetDeploymentAttachments } from "@/controllers/API/queries/deployments/use-get-deployment-attachments";
import { useGetDeployments } from "@/controllers/API/queries/deployments/use-get-deployments";
import { useErrorAlert } from "@/pages/MainPage/pages/deploymentsPage/hooks/use-error-alert";
import type {
  DeploymentProvider,
  ProviderAccount,
} from "@/pages/MainPage/pages/deploymentsPage/types";
import DeploymentPhaseContent, {
  NEW_DEPLOYMENT_VALUE,
} from "./deployment-phase";
import ProviderPhaseContent from "./provider-phase";
import ReviewPhaseContent from "./review-phase";
import { type FlowAttachment, toReviewAttachment } from "./types";
import UpdatePhaseContent from "./update-phase";

const PROVIDER_KEY_MAP: Record<string, DeploymentProvider> = {
  "watsonx-orchestrate": {
    id: "watsonx",
    type: "watsonx",
    name: "watsonx Orchestrate",
    icon: "Bot",
  },
};

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

type Phase = "provider" | "deployments" | "review";

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
  const [phase, setPhase] = useState<Phase>("provider");
  const [selectedProviderId, setSelectedProviderId] =
    useState<string>(NEW_DEPLOYMENT_VALUE);
  const [selectedDeployment, setSelectedDeployment] =
    useState<string>(NEW_DEPLOYMENT_VALUE);
  const [reviewAttachment, setReviewAttachment] =
    useState<FlowAttachment | null>(null);
  const [updatePhase, setUpdatePhase] = useState<
    "idle" | "updating" | "updated"
  >("idle");
  const [updatedDeploymentName, setUpdatedDeploymentName] = useState("");
  const [updatedDeploymentId, setUpdatedDeploymentId] = useState("");
  const showError = useErrorAlert();
  const { mutateAsync: patchSnapshot } = usePatchSnapshot();

  const selectedProvider = useMemo(
    () => providers.find((p) => p.id === selectedProviderId) ?? null,
    [providers, selectedProviderId],
  );

  const shouldFetchDeployments =
    open && phase === "deployments" && !!selectedProvider;
  const { data: deploymentsData, isLoading: isLoadingDeployments } =
    useGetDeployments(
      {
        provider_id: selectedProvider?.id ?? "",
        flow_ids: flowId,
        page: 1,
        size: 50,
      },
      { enabled: shouldFetchDeployments },
    );

  const deployments = useMemo(
    () => deploymentsData?.deployments ?? [],
    [deploymentsData],
  );

  const selectedDeploymentEntry = useMemo(
    () =>
      deployments.find((deployment) => deployment.id === selectedDeployment),
    [deployments, selectedDeployment],
  );

  const shouldFetchSelectedDeploymentAttachments =
    open &&
    phase === "review" &&
    !!selectedProvider &&
    selectedDeployment !== NEW_DEPLOYMENT_VALUE &&
    !!selectedDeploymentEntry;

  const {
    data: selectedDeploymentAttachmentsData,
    isLoading: isLoadingSelectedDeploymentAttachments,
    isFetching: isFetchingSelectedDeploymentAttachments,
  } = useGetDeploymentAttachments(
    {
      deploymentId: selectedDeploymentEntry?.id ?? "",
      flow_ids: flowId,
    },
    { enabled: shouldFetchSelectedDeploymentAttachments },
  );

  useEffect(() => {
    if (deployments.length === 1) {
      setSelectedDeployment(deployments[0].id);
    } else {
      setSelectedDeployment(NEW_DEPLOYMENT_VALUE);
    }
  }, [deployments]);

  useEffect(() => {
    if (
      phase !== "review" ||
      selectedDeployment === NEW_DEPLOYMENT_VALUE ||
      !selectedDeploymentEntry
    ) {
      return;
    }
    if (
      isLoadingSelectedDeploymentAttachments ||
      isFetchingSelectedDeploymentAttachments
    ) {
      return;
    }

    const nextReviewAttachment = toReviewAttachment(
      selectedDeploymentEntry,
      selectedDeploymentAttachmentsData?.flow_versions ?? [],
    );
    if (!nextReviewAttachment) {
      showError(
        "Failed to load deployment details",
        "No provider snapshot was found for this flow on the selected deployment.",
      );
      setPhase("deployments");
      setReviewAttachment(null);
      return;
    }
    setReviewAttachment(nextReviewAttachment);
  }, [
    phase,
    selectedDeployment,
    selectedDeploymentEntry,
    selectedDeploymentAttachmentsData,
    isLoadingSelectedDeploymentAttachments,
    isFetchingSelectedDeploymentAttachments,
    showError,
  ]);

  useEffect(() => {
    if (!open) return;

    if (providers.length === 1) {
      setSelectedProviderId(providers[0].id);
      setPhase("deployments");
    } else {
      setSelectedProviderId(providers[0]?.id ?? "");
      setPhase("provider");
    }
    setSelectedDeployment(NEW_DEPLOYMENT_VALUE);
    setReviewAttachment(null);
    setUpdatePhase("idle");
    setUpdatedDeploymentId("");
    setUpdatedDeploymentName("");
  }, [open, providers]);

  const buildProviderPreselection = useCallback(() => {
    if (!selectedProvider) return undefined;
    const mappedProvider = PROVIDER_KEY_MAP[selectedProvider.provider_key];
    if (!mappedProvider) return undefined;
    return {
      provider: mappedProvider,
      instance: selectedProvider,
    };
  }, [selectedProvider]);

  const handleProviderContinue = () => {
    setPhase("deployments");
  };

  const handleDeploymentContinue = () => {
    if (selectedDeployment === NEW_DEPLOYMENT_VALUE) {
      onChooseNew(buildProviderPreselection());
      return;
    }
    if (!selectedDeploymentEntry) return;
    setReviewAttachment(null);
    setPhase("review");
  };

  const handleReviewConfirm = async () => {
    if (!reviewAttachment) return;

    setUpdatePhase("updating");
    try {
      await patchSnapshot({
        providerSnapshotId: reviewAttachment.provider_snapshot_id,
        flowVersionId: snapshotVersionId,
      });
      setUpdatedDeploymentId(reviewAttachment.deployment_id);
      setUpdatedDeploymentName(reviewAttachment.deployment_name);
      setUpdatePhase("updated");
    } catch (err: unknown) {
      setUpdatePhase("idle");
      showError("Failed to update deployment", err);
    }
  };

  const handleBack = () => {
    if (phase === "review") {
      setPhase("deployments");
      setReviewAttachment(null);
      return;
    }
    setPhase("provider");
    setSelectedDeployment(NEW_DEPLOYMENT_VALUE);
  };

  const isUpdating = updatePhase === "updating";
  const isUpdated = updatePhase === "updated";
  const isInUpdatePhase = isUpdating || isUpdated;
  const isLoadingReviewAttachment =
    phase === "review" &&
    (isLoadingSelectedDeploymentAttachments ||
      isFetchingSelectedDeploymentAttachments);
  const isBusy =
    isUpdating || isLoadingDeployments || isLoadingReviewAttachment;

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
      <DialogContent className="max-w-md">
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
        ) : phase === "review" && reviewAttachment ? (
          <ReviewPhaseContent
            attachment={reviewAttachment}
            flowId={flowId}
            newVersionTag={snapshotVersionTag}
            isBusy={isBusy}
            onBack={handleBack}
            onConfirm={handleReviewConfirm}
            onCancel={() => setOpen(false)}
          />
        ) : phase === "review" && isLoadingReviewAttachment ? (
          <div className="flex min-h-52 items-center justify-center">
            <div className="text-sm text-muted-foreground">
              Loading deployment attachment details...
            </div>
          </div>
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
