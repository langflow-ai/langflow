import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useGetProviderAccounts } from "@/controllers/API/queries/deployment-provider-accounts/use-get-provider-accounts";
import { useDeleteDeployment } from "@/controllers/API/queries/deployments/use-delete-deployment";
import { useGetDeployments } from "@/controllers/API/queries/deployments/use-get-deployments";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import useAlertStore from "@/stores/alertStore";
import DeploymentStepperModal from "./components/deployment-stepper-modal";
import DeploymentsContent from "./components/deployments-content";
import SubTabToggle, {
  type DeploymentSubTab,
} from "./components/sub-tab-toggle";
import TestDeploymentModal from "./components/test-deployment-modal/test-deployment-modal";
import type { Deployment } from "./types";

export default function DeploymentsPage() {
  const [activeSubTab, setActiveSubTab] =
    useState<DeploymentSubTab>("deployments");
  const [stepperOpen, setStepperOpen] = useState(false);
  const [testTarget, setTestTarget] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [testProviderId, setTestProviderId] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<Deployment | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const setErrorData = useAlertStore((state) => state.setErrorData);

  const { data: providersData } = useGetProviderAccounts({});
  const providers = providersData?.providers ?? [];
  const firstProviderId = providers[0]?.id ?? "";

  const { data, isLoading } = useGetDeployments(
    { provider_id: firstProviderId },
    { enabled: !!firstProviderId },
  );
  const deployments = data?.deployments ?? [];
  const isEmpty = !firstProviderId || deployments.length === 0;

  const { mutate: deleteDeployment } = useDeleteDeployment();

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

  return (
    <div className="flex flex-col gap-4 pt-4">
      <div className="flex items-center justify-between">
        <SubTabToggle activeTab={activeSubTab} onTabChange={setActiveSubTab} />
        <Button
          onClick={() => setStepperOpen(true)}
          data-testid="new-deployment-btn"
        >
          <ForwardedIconComponent name="Plus" className="h-4 w-4" />
          New Deployment
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
          onDeleteDeployment={setDeleteTarget}
        />
      )}

      {activeSubTab === "providers" && (
        <div className="py-24 text-center text-sm text-muted-foreground">
          Deployment Providers coming soon
        </div>
      )}

      <DeploymentStepperModal
        open={stepperOpen}
        setOpen={setStepperOpen}
        onTestDeployment={(deployment, providerId) => {
          setTestTarget(deployment);
          setTestProviderId(providerId);
        }}
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
