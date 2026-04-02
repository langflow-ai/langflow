import { useState } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useDeleteDeployment } from "@/controllers/API/queries/deployments/use-delete-deployment";
import { useGetDeploymentsByProviders } from "@/controllers/API/queries/deployments/use-get-deployments-by-providers";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import { useDeleteWithConfirmation } from "../hooks/use-delete-with-confirmation";
import { ALL_PROVIDERS, useProviderFilter } from "../hooks/use-provider-filter";
import { useTestDeploymentModal } from "../hooks/use-test-deployment-modal";
import type { Deployment, ProviderAccount } from "../types";
import DeploymentStepperModal from "./deployment-stepper-modal";
import DeploymentsEmptyState from "./deployments-empty-state";
import DeploymentsLoadingSkeleton from "./deployments-loading-skeleton";
import DeploymentsTable from "./deployments-table";
import TestDeploymentModal from "./test-deployment-modal/test-deployment-modal";

const buildDeploymentDeleteParams = (id: string) => ({ deployment_id: id });

interface DeploymentsContentProps {
  isLoadingProviders: boolean;
  providers: ProviderAccount[];
  stepperOpen: boolean;
  setStepperOpen: (open: boolean) => void;
}

export default function DeploymentsContent({
  isLoadingProviders,
  providers,
  stepperOpen,
  setStepperOpen,
}: DeploymentsContentProps) {
  const {
    selectedProviderId,
    setSelectedProviderId,
    providerIdsToQuery,
    providerMap,
  } = useProviderFilter(providers);

  const { deployments, isLoading: isLoadingDeployments } =
    useGetDeploymentsByProviders(providerIdsToQuery);

  const testModal = useTestDeploymentModal();

  const { mutate: deleteDeployment } = useDeleteDeployment();

  const deploymentDelete = useDeleteWithConfirmation(
    deleteDeployment,
    buildDeploymentDeleteParams,
    "Error deleting deployment",
  );

  const [editingDeployment, setEditingDeployment] = useState<Deployment | null>(
    null,
  );

  const isLoading = isLoadingProviders || isLoadingDeployments;
  const hasProviders = providers.length > 0;
  const isEmpty = !hasProviders || deployments.length === 0;

  const content = (() => {
    if (isLoading) return <DeploymentsLoadingSkeleton />;
    if (isEmpty)
      return (
        <DeploymentsEmptyState
          onCreateDeployment={() => setStepperOpen(true)}
        />
      );
    return (
      <DeploymentsTable
        deployments={deployments}
        providerMap={providerMap}
        deletingId={deploymentDelete.deletingId}
        onTestDeployment={testModal.handleTestDeployment}
        onUpdateDeployment={(deployment) => {
          setEditingDeployment(deployment);
          setStepperOpen(true);
        }}
        onDeleteDeployment={deploymentDelete.requestDelete}
      />
    );
  })();

  return (
    <>
      {providers.length > 1 && (
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Environment:</span>
          <Select
            value={selectedProviderId}
            onValueChange={setSelectedProviderId}
          >
            <SelectTrigger className="w-[220px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_PROVIDERS}>All environments</SelectItem>
              {providers.map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  {p.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {content}

      <DeploymentStepperModal
        open={stepperOpen}
        setOpen={(open) => {
          setStepperOpen(open);
          if (!open) setEditingDeployment(null);
        }}
        onTestDeployment={testModal.handleTestFromStepper}
        editingDeployment={editingDeployment}
        initialInstance={
          editingDeployment?.provider_account_id
            ? providers.find(
                (p) => p.id === editingDeployment.provider_account_id,
              )
            : undefined
        }
      />

      <TestDeploymentModal
        open={testModal.open}
        setOpen={testModal.setOpen}
        deployment={testModal.testTarget}
        providerId={testModal.testProviderId}
      />

      <DeleteConfirmationModal
        open={!!deploymentDelete.target}
        setOpen={deploymentDelete.setModalOpen}
        description={`deployment "${deploymentDelete.target?.name}"`}
        onConfirm={deploymentDelete.confirmDelete}
      />
    </>
  );
}
