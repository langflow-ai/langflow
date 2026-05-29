import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useDeleteDeployment } from "@/controllers/API/queries/deployments/use-delete-deployment";
import { useDeleteWithConfirmation } from "../hooks/use-delete-with-confirmation";
import { useTestDeploymentModal } from "../hooks/use-test-deployment-modal";
import { type Deployment, type ProviderAccount } from "../types";
import DeploymentDetailsModal from "./deployment-details-modal/deployment-details-modal";
import DeploymentStepperModal from "./deployment-stepper-modal";
import DeploymentsEmptyState from "./deployments-empty-state";
import DeploymentsLoadingSkeleton from "./deployments-loading-skeleton";
import DeploymentsTable from "./deployments-table";
import TestDeploymentModal from "./test-deployment-modal/test-deployment-modal";
import TypeToConfirmDeleteDialog from "./type-to-confirm-delete-dialog";

const buildDeploymentDeleteParams = (id: string) => ({ deployment_id: id });

interface DeploymentsContentProps {
  providers: ProviderAccount[];
  deployments: Deployment[];
  isLoading: boolean;
  providerMap: Record<string, string>;
  stepperOpen: boolean;
  setStepperOpen: (open: boolean) => void;
}

export default function DeploymentsContent({
  providers,
  deployments,
  isLoading,
  providerMap,
  stepperOpen,
  setStepperOpen,
}: DeploymentsContentProps) {
  const { t } = useTranslation();
  const testModal = useTestDeploymentModal();

  const { mutate: deleteDeployment } = useDeleteDeployment();

  const deploymentDelete = useDeleteWithConfirmation<
    Deployment,
    { deployment_id: string }
  >(
    deleteDeployment,
    buildDeploymentDeleteParams,
    t("deployments.errorDeletingDeployment"),
  );

  const [editingDeployment, setEditingDeployment] = useState<Deployment | null>(
    null,
  );

  const [detailsDeployment, setDetailsDeployment] = useState<Deployment | null>(
    null,
  );

  const content = (() => {
    if (isLoading) return <DeploymentsLoadingSkeleton />;
    if (deployments.length === 0)
      return <DeploymentsEmptyState onAction={() => setStepperOpen(true)} />;
    return (
      <DeploymentsTable
        deployments={deployments}
        providerMap={providerMap}
        deletingId={deploymentDelete.deletingId}
        onTestDeployment={testModal.handleTestDeployment}
        onViewDetails={(deployment) => setDetailsDeployment(deployment)}
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
          editingDeployment?.provider_id
            ? providers.find((p) => p.id === editingDeployment.provider_id)
            : undefined
        }
      />

      <TestDeploymentModal
        open={testModal.open}
        setOpen={testModal.setOpen}
        deployment={testModal.testTarget}
        providerId={testModal.testProviderId}
      />

      <DeploymentDetailsModal
        open={!!detailsDeployment}
        setOpen={(open) => {
          if (!open) setDetailsDeployment(null);
        }}
        deployment={detailsDeployment}
        providerName={
          detailsDeployment
            ? (providerMap[detailsDeployment.provider_id ?? ""] ?? "—")
            : ""
        }
      />

      <TypeToConfirmDeleteDialog
        open={!!deploymentDelete.target}
        onOpenChange={deploymentDelete.setModalOpen}
        deploymentName={deploymentDelete.target?.name ?? ""}
        onConfirm={deploymentDelete.confirmDelete}
      />
    </>
  );
}
