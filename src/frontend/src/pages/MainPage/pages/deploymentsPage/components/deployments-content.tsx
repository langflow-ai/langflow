import type { Deployment } from "../types";
import DeploymentsEmptyState from "./deployments-empty-state";
import DeploymentsLoadingSkeleton from "./deployments-loading-skeleton";
import DeploymentsTable from "./deployments-table";

interface DeploymentsContentProps {
  isLoading: boolean;
  isEmpty: boolean;
  deployments: Deployment[];
  providerName: string;
  deletingId?: string | null;
  onCreateDeployment: () => void;
  onTestDeployment: (deployment: Deployment) => void;
  onUpdateDeployment: (deployment: Deployment) => void;
  onDeleteDeployment: (deployment: Deployment) => void;
}

export default function DeploymentsContent({
  isLoading,
  isEmpty,
  deployments,
  providerName,
  deletingId,
  onCreateDeployment,
  onTestDeployment,
  onUpdateDeployment,
  onDeleteDeployment,
}: DeploymentsContentProps) {
  if (isLoading) return <DeploymentsLoadingSkeleton />;
  if (isEmpty)
    return <DeploymentsEmptyState onCreateDeployment={onCreateDeployment} />;
  return (
    <DeploymentsTable
      deployments={deployments}
      providerName={providerName}
      deletingId={deletingId}
      onTestDeployment={onTestDeployment}
      onUpdateDeployment={onUpdateDeployment}
      onDeleteDeployment={onDeleteDeployment}
    />
  );
}
