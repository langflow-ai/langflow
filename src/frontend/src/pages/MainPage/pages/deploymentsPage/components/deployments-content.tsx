import type { Deployment } from "../types";
import DeploymentsEmptyState from "./deployments-empty-state";
import DeploymentsLoadingSkeleton from "./deployments-loading-skeleton";
import DeploymentsTable from "./deployments-table";

interface DeploymentsContentProps {
  isLoading: boolean;
  isEmpty: boolean;
  deployments: Deployment[];
  providerMap: Record<string, string>;
  deletingId?: string | null;
  onCreateDeployment: () => void;
  onTestDeployment: (deployment: Deployment) => void;
  onDeleteDeployment: (deployment: Deployment) => void;
}

export default function DeploymentsContent({
  isLoading,
  isEmpty,
  deployments,
  providerMap,
  deletingId,
  onCreateDeployment,
  onTestDeployment,
  onDeleteDeployment,
}: DeploymentsContentProps) {
  if (isLoading) return <DeploymentsLoadingSkeleton />;
  if (isEmpty)
    return <DeploymentsEmptyState onCreateDeployment={onCreateDeployment} />;
  return (
    <DeploymentsTable
      deployments={deployments}
      providerMap={providerMap}
      deletingId={deletingId}
      onTestDeployment={onTestDeployment}
      onDeleteDeployment={onDeleteDeployment}
    />
  );
}
