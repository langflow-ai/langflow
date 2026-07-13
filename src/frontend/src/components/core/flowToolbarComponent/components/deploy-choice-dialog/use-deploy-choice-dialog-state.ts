import { useCallback, useEffect, useMemo, useState } from "react";
import { usePatchSnapshot } from "@/controllers/API/queries/deployments";
import { useGetDeploymentAttachments } from "@/controllers/API/queries/deployments/use-get-deployment-attachments";
import { useGetDeployments } from "@/controllers/API/queries/deployments/use-get-deployments";
import i18n from "@/i18n";
import { useErrorAlert } from "@/pages/MainPage/pages/deploymentsPage/hooks/use-error-alert";
import type {
  DeploymentProvider,
  ProviderAccount,
} from "@/pages/MainPage/pages/deploymentsPage/types";
import { NEW_DEPLOYMENT_VALUE } from "./deployment-phase";
import { type FlowAttachment, toReviewAttachments } from "./types";

const PROVIDER_KEY_MAP: Record<string, DeploymentProvider> = {
  "watsonx-orchestrate": {
    id: "watsonx",
    type: "watsonx",
    name: "watsonx Orchestrate",
    icon: "Bot",
  },
};

type Phase = "provider" | "deployments" | "review";

interface UseDeployChoiceDialogStateParams {
  open: boolean;
  providers: ProviderAccount[];
  flowId: string;
  snapshotVersionId: string;
  onChooseNew: (preselected?: {
    provider: DeploymentProvider;
    instance: ProviderAccount;
  }) => void;
}

export function useDeployChoiceDialogState({
  open,
  providers,
  flowId,
  snapshotVersionId,
  onChooseNew,
}: UseDeployChoiceDialogStateParams) {
  const [phase, setPhase] = useState<Phase>("provider");
  const [selectedProviderId, setSelectedProviderId] =
    useState<string>(NEW_DEPLOYMENT_VALUE);
  const [selectedDeployment, setSelectedDeployment] =
    useState<string>(NEW_DEPLOYMENT_VALUE);
  const [reviewAttachments, setReviewAttachments] = useState<FlowAttachment[]>(
    [],
  );
  const [reviewAttachment, setReviewAttachment] =
    useState<FlowAttachment | null>(null);
  const [hasInitializedOpenState, setHasInitializedOpenState] = useState(false);
  const [updatePhase, setUpdatePhase] = useState<
    "idle" | "updating" | "updated"
  >("idle");
  const [updatedDeploymentName, setUpdatedDeploymentName] = useState("");
  const [updatedDeploymentId, setUpdatedDeploymentId] = useState("");
  const showError = useErrorAlert();
  const { mutateAsync: patchSnapshot } = usePatchSnapshot();

  const selectedProvider = useMemo(
    () =>
      providers.find((provider) => provider.id === selectedProviderId) ?? null,
    [providers, selectedProviderId],
  );

  const shouldFetchDeployments =
    open && phase === "deployments" && !!selectedProvider;
  const { data: deploymentsData, isLoading: isLoadingDeployments } =
    useGetDeployments(
      {
        provider_id: selectedProvider?.id ?? "",
        flow_ids: [flowId],
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
      deployments.find((deployment) => deployment.id === selectedDeployment) ??
      null,
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
      flow_ids: [flowId],
    },
    { enabled: shouldFetchSelectedDeploymentAttachments },
  );

  useEffect(() => {
    setSelectedDeployment((current) => {
      if (deployments.length === 1) {
        return deployments[0].id;
      }
      if (
        current !== NEW_DEPLOYMENT_VALUE &&
        deployments.some((deployment) => deployment.id === current)
      ) {
        return current;
      }
      return NEW_DEPLOYMENT_VALUE;
    });
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

    const nextReviewAttachments = toReviewAttachments(
      selectedDeploymentEntry,
      selectedDeploymentAttachmentsData?.flow_versions ?? [],
      i18n.t("deployments.unknownFlow"),
    );
    if (nextReviewAttachments.length === 0) {
      showError(
        i18n.t("errors.failedToLoadDeployment"),
        i18n.t("errors.noProviderSnapshotFoundOnSelectedDeployment"),
      );
      setPhase("deployments");
      setReviewAttachments([]);
      setReviewAttachment(null);
      return;
    }
    setReviewAttachments(nextReviewAttachments);
    setReviewAttachment((current) => {
      if (!current) {
        return nextReviewAttachments[0];
      }
      return (
        nextReviewAttachments.find(
          (item) => item.provider_snapshot_id === current.provider_snapshot_id,
        ) ?? nextReviewAttachments[0]
      );
    });
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
    if (!open) {
      setHasInitializedOpenState(false);
      return;
    }

    if (providers.length === 1) {
      setSelectedProviderId(providers[0].id);
      setPhase("deployments");
    } else {
      setSelectedProviderId(providers[0]?.id ?? "");
      setPhase("provider");
    }
    setSelectedDeployment(NEW_DEPLOYMENT_VALUE);
    setReviewAttachments([]);
    setReviewAttachment(null);
    setUpdatePhase("idle");
    setUpdatedDeploymentId("");
    setUpdatedDeploymentName("");
    setHasInitializedOpenState(true);
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

  useEffect(() => {
    if (!open || phase !== "deployments" || isLoadingDeployments) return;
    if (!hasInitializedOpenState) return;
    if (!selectedProvider) return;
    if (deployments.length > 0) return;

    onChooseNew(buildProviderPreselection());
  }, [
    open,
    phase,
    isLoadingDeployments,
    hasInitializedOpenState,
    selectedProvider,
    deployments,
    onChooseNew,
    buildProviderPreselection,
  ]);

  const handleProviderContinue = useCallback(() => {
    setPhase("deployments");
  }, []);

  const handleDeploymentContinue = useCallback(() => {
    if (selectedDeployment === NEW_DEPLOYMENT_VALUE) {
      onChooseNew(buildProviderPreselection());
      return;
    }
    if (!selectedDeploymentEntry) return;
    setReviewAttachments([]);
    setReviewAttachment(null);
    setPhase("review");
  }, [
    selectedDeployment,
    onChooseNew,
    buildProviderPreselection,
    selectedDeploymentEntry,
  ]);

  const handleReviewConfirm = useCallback(async () => {
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
      showError(i18n.t("deployments.failedToUpdateDeployment"), err);
    }
  }, [patchSnapshot, reviewAttachment, showError, snapshotVersionId]);

  const handleBack = useCallback(() => {
    if (phase === "review") {
      setPhase("deployments");
      setReviewAttachments([]);
      setReviewAttachment(null);
      return;
    }
    setPhase("provider");
    setSelectedDeployment(NEW_DEPLOYMENT_VALUE);
  }, [phase]);

  const handleSelectAttachment = useCallback(
    (providerSnapshotId: string) => {
      const nextAttachment =
        reviewAttachments.find(
          (item) => item.provider_snapshot_id === providerSnapshotId,
        ) ?? null;
      setReviewAttachment(nextAttachment);
    },
    [reviewAttachments],
  );

  const isUpdating = updatePhase === "updating";
  const isUpdated = updatePhase === "updated";
  const isInUpdatePhase = isUpdating || isUpdated;
  const isLoadingReviewAttachment =
    phase === "review" &&
    (isLoadingSelectedDeploymentAttachments ||
      isFetchingSelectedDeploymentAttachments);
  const isBusy =
    isUpdating || isLoadingDeployments || isLoadingReviewAttachment;

  return {
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
  };
}
