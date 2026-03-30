import type { Deployment } from "../types";
import DeploymentsEmptyState from "./deployments-empty-state";
import DeploymentsLoadingSkeleton from "./deployments-loading-skeleton";
import DeploymentsTable from "./deployments-table";

interface DeploymentsContentProps {
  isLoading: boolean;
  isEmpty: boolean;
  deployments: Deployment[];
  providerName: string;
  onCreateDeployment: () => void;
}

export default function DeploymentsContent({
  isLoading,
  isEmpty,
  deployments,
  providerName,
  onCreateDeployment,
}: DeploymentsContentProps) {
  if (isLoading) return <DeploymentsLoadingSkeleton />;
  if (isEmpty)
    return <DeploymentsEmptyState onCreateDeployment={onCreateDeployment} />;
  return (
    <DeploymentsTable deployments={deployments} providerName={providerName} />
  );
}
