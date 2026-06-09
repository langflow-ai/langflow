import { useState } from "react";
import { useGetProviderAccounts } from "@/controllers/API/queries/deployment-provider-accounts/use-get-provider-accounts";
import { usePostCreateSnapshot } from "@/controllers/API/queries/flow-version/use-post-create-snapshot";
import useSaveFlow from "@/hooks/flows/use-save-flow";
import { useErrorAlert } from "@/pages/MainPage/pages/deploymentsPage/hooks/use-error-alert";
import type {
  DeploymentProvider,
  ProviderAccount,
} from "@/pages/MainPage/pages/deploymentsPage/types";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";

export function usePrepareDeploy() {
  const [isPreparingDeploy, setIsPreparingDeploy] = useState(false);
  const [deployModalOpen, setDeployModalOpen] = useState(false);
  const [choiceDialogOpen, setChoiceDialogOpen] = useState(false);
  const [providers, setProviders] = useState<ProviderAccount[]>([]);
  const [pendingSnapshotVersionId, setPendingSnapshotVersionId] = useState("");
  const [initialVersionByFlow, setInitialVersionByFlow] = useState<
    Map<string, { versionId: string; versionTag: string }>
  >(new Map());
  const [stepperInitialProvider, setStepperInitialProvider] = useState<
    DeploymentProvider | undefined
  >();
  const [stepperInitialInstance, setStepperInitialInstance] = useState<
    ProviderAccount | undefined
  >();

  const currentFlowId = useFlowStore((state) => state.currentFlow?.id);
  const saveFlow = useSaveFlow();
  const { mutateAsync: createSnapshot } = usePostCreateSnapshot();
  const { refetch: fetchProviderAccounts } = useGetProviderAccounts(
    { page: 1, size: 50 },
    { enabled: false },
  );
  const showError = useErrorAlert();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  const handleDeploy = async () => {
    if (!currentFlowId) return;
    setIsPreparingDeploy(true);
    try {
      await saveFlow();
      const snapshot = await createSnapshot({ flowId: currentFlowId });
      const versionMap = new Map<
        string,
        { versionId: string; versionTag: string }
      >();
      versionMap.set(currentFlowId, {
        versionId: snapshot.id,
        versionTag: snapshot.version_tag,
      });
      setInitialVersionByFlow(versionMap);
      setPendingSnapshotVersionId(snapshot.id);

      const { data } = await fetchProviderAccounts();
      const providerList = data?.provider_accounts ?? [];

      if (providerList.length === 0) {
        setStepperInitialProvider(undefined);
        setStepperInitialInstance(undefined);
        setDeployModalOpen(true);
      } else {
        setProviders(providerList);
        setChoiceDialogOpen(true);
      }
    } catch (err: unknown) {
      setPendingSnapshotVersionId("");
      showError("Failed to prepare deployment", err);
    } finally {
      setIsPreparingDeploy(false);
    }
  };

  const handleChooseNew = (preselected?: {
    provider: DeploymentProvider;
    instance: ProviderAccount;
  }) => {
    setChoiceDialogOpen(false);
    setStepperInitialProvider(preselected?.provider);
    setStepperInitialInstance(preselected?.instance);
    setDeployModalOpen(true);
  };

  const handleUpdateComplete = (deploymentName: string) => {
    setChoiceDialogOpen(false);
    setProviders([]);
    setPendingSnapshotVersionId("");
    setSuccessData({
      title: `Deployment "${deploymentName}" updated successfully`,
    });
  };

  const resetChoiceState = () => {
    setChoiceDialogOpen(false);
    setProviders([]);
    setPendingSnapshotVersionId("");
  };

  return {
    currentFlowId,
    isPreparingDeploy,
    choiceDialogOpen,
    setChoiceDialogOpen,
    deployModalOpen,
    setDeployModalOpen,
    providers,
    pendingSnapshotVersionId,
    initialVersionByFlow,
    stepperInitialProvider,
    stepperInitialInstance,
    handleDeploy,
    handleChooseNew,
    handleUpdateComplete,
    resetChoiceState,
  };
}
