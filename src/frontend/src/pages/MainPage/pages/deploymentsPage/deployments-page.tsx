import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useDeleteProviderAccount } from "@/controllers/API/queries/deployment-provider-accounts/use-delete-provider-account";
import { useGetProviderAccounts } from "@/controllers/API/queries/deployment-provider-accounts/use-get-provider-accounts";
import { useDeleteDeployment } from "@/controllers/API/queries/deployments/use-delete-deployment";
import { useGetDeployments } from "@/controllers/API/queries/deployments/use-get-deployments";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import useAlertStore from "@/stores/alertStore";
import AddProviderModal from "./components/add-provider-modal";
import DeploymentStepperModal from "./components/deployment-stepper-modal";
import DeploymentsContent from "./components/deployments-content";
import ProvidersContent from "./components/providers-content";
import SubTabToggle, {
  type DeploymentSubTab,
} from "./components/sub-tab-toggle";
import TestDeploymentModal from "./components/test-deployment-modal/test-deployment-modal";
import type { Deployment, ProviderAccount } from "./types";

export default function DeploymentsPage() {
  const [activeSubTab, setActiveSubTab] =
    useState<DeploymentSubTab>("deployments");
  const [stepperOpen, setStepperOpen] = useState(false);
  const [addProviderOpen, setAddProviderOpen] = useState(false);
  const [testTarget, setTestTarget] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [testProviderId, setTestProviderId] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<Deployment | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteProviderTarget, setDeleteProviderTarget] =
    useState<ProviderAccount | null>(null);
  const [deletingProviderId, setDeletingProviderId] = useState<string | null>(
    null,
  );

  // Edit mode state
  const [editingDeployment, setEditingDeployment] =
    useState<Deployment | null>(null);

  const location = useLocation();
  const setErrorData = useAlertStore((state) => state.setErrorData);

  // Auto-open test modal when navigated from canvas deploy button
  useEffect(() => {
    const state = location.state as {
      testDeployment?: { id: string; name: string };
      testProviderId?: string;
    } | null;
    if (state?.testDeployment && state?.testProviderId) {
      setTestTarget(state.testDeployment);
      setTestProviderId(state.testProviderId);
      // Clear the state so it doesn't re-trigger on re-renders
      window.history.replaceState({}, "");
    }
  }, [location.state]);

  const { data: providersData, isLoading: isLoadingProviders } =
    useGetProviderAccounts({});
  const providers = providersData?.providers ?? [];
  const firstProviderId = providers[0]?.id ?? "";
  const firstProvider = providers[0] ?? null;

  const { data, isLoading } = useGetDeployments(
    { provider_id: firstProviderId },
    { enabled: !!firstProviderId },
  );
  const deployments = data?.deployments ?? [];
  const isEmpty = !firstProviderId || deployments.length === 0;

  const { mutate: deleteDeployment } = useDeleteDeployment();
  const { mutate: deleteProviderAccount } = useDeleteProviderAccount();

  function handleConfirmDelete(
    e: React.MouseEvent<HTMLButtonElement, MouseEvent>,
  ) {
    e.stopPropagation();
    if (!deleteTarget) return;
    setDeletingId(deleteTarget.id);
    setDeleteTarget(null);
    deleteDeployment(
      { deployment_id: deleteTarget.id },
      {
        onError: () => {
          setErrorData({
            title: "Error deleting deployment",
            list: [`Failed to delete "${deleteTarget.name}"`],
          });
        },
        onSettled: () => setDeletingId(null),
      },
    );
  }

  function handleConfirmDeleteProvider(
    e: React.MouseEvent<HTMLButtonElement, MouseEvent>,
  ) {
    e.stopPropagation();
    if (!deleteProviderTarget) return;
    setDeletingProviderId(deleteProviderTarget.id);
    setDeleteProviderTarget(null);
    deleteProviderAccount(
      { provider_id: deleteProviderTarget.id },
      {
        onError: () => {
          setErrorData({
            title: "Error deleting environment",
            list: [`Failed to delete "${deleteProviderTarget.name}"`],
          });
        },
        onSettled: () => setDeletingProviderId(null),
      },
    );
  }

  function handleUpdateDeployment(deployment: Deployment) {
    setEditingDeployment(deployment);
    setStepperOpen(true);
  }

  function handleStepperClose(open: boolean) {
    setStepperOpen(open);
    if (!open) {
      // Clear editing state when modal closes
      setEditingDeployment(null);
    }
  }

  return (
    <div className="flex flex-col gap-4 pt-4">
      <div className="flex items-center justify-between">
        <SubTabToggle activeTab={activeSubTab} onTabChange={setActiveSubTab} />
        <Button
          onClick={() =>
            activeSubTab === "providers"
              ? setAddProviderOpen(true)
              : setStepperOpen(true)
          }
          data-testid={
            activeSubTab === "providers"
              ? "new-provider-btn"
              : "new-deployment-btn"
          }
        >
          <ForwardedIconComponent name="Plus" className="h-4 w-4" />
          {activeSubTab === "providers" ? "New Environment" : "New Deployment"}
        </Button>
      </div>

      {activeSubTab === "deployments" && (
        <DeploymentsContent
          isLoading={isLoading}
          isEmpty={isEmpty}
          deployments={deployments}
          providerName={providers[0]?.name ?? ""}
          deletingId={deletingId}
          onCreateDeployment={() => setStepperOpen(true)}
          onTestDeployment={(deployment) => {
            setTestTarget(deployment);
            setTestProviderId(firstProviderId);
          }}
          onUpdateDeployment={handleUpdateDeployment}
          onDeleteDeployment={setDeleteTarget}
        />
      )}

      {activeSubTab === "providers" && (
        <ProvidersContent
          isLoading={isLoadingProviders}
          providers={providers}
          deletingId={deletingProviderId}
          onAddProvider={() => setAddProviderOpen(true)}
          onDeleteProvider={setDeleteProviderTarget}
        />
      )}

      <DeploymentStepperModal
        open={stepperOpen}
        setOpen={handleStepperClose}
        onTestDeployment={(deployment, providerId) => {
          setTestTarget(deployment);
          setTestProviderId(providerId);
        }}
        editingDeployment={editingDeployment}
        editingProviderAccount={firstProvider}
      />

      <TestDeploymentModal
        open={!!testTarget}
        setOpen={(open) => {
          if (!open) {
            setTestTarget(null);
            setTestProviderId("");
          }
        }}
        deployment={testTarget}
        providerId={testProviderId}
      />

      <AddProviderModal open={addProviderOpen} setOpen={setAddProviderOpen} />

      <DeleteConfirmationModal
        open={!!deleteProviderTarget}
        setOpen={(open) => {
          if (!open) setDeleteProviderTarget(null);
        }}
        description={`environment "${deleteProviderTarget?.name}"`}
        onConfirm={handleConfirmDeleteProvider}
      />

      <DeleteConfirmationModal
        open={!!deleteTarget}
        setOpen={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        description={`deployment "${deleteTarget?.name}"`}
        onConfirm={handleConfirmDelete}
      />
    </div>
  );
}
