import type { DeploymentProvider } from "@/controllers/API/queries/deployments/use-deployments";
import {
  type DeploymentListRow,
  DeploymentProvidersView,
} from "./DeploymentProvidersView";

type DeploymentsViewProps = {
  providers: DeploymentProvider[];
  deploymentRows: DeploymentListRow[];
  selectedProviderId: string | null;
  onSelectProvider: (providerId: string) => void;
  onConfigureProvider: (provider: DeploymentProvider) => void;
  selectedProviderDeploymentCount: number;
  isLoadingDeployments: boolean;
  isLoadingProviders: boolean;
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onCreateDeployment: () => void;
  activeSubTab: "deployments" | "providers";
  onTestAgent: (deployment: {
    id: string;
    name: string;
    deploymentType: "agent" | "mcp";
    mode?: string;
  }) => void;
};

export const DeploymentsView = ({
  providers,
  deploymentRows,
  selectedProviderId,
  onSelectProvider,
  onConfigureProvider,
  selectedProviderDeploymentCount,
  isLoadingDeployments,
  isLoadingProviders,
  page,
  pageSize,
  total,
  onPageChange,
  onCreateDeployment,
  activeSubTab,
  onTestAgent,
}: DeploymentsViewProps) => {
  return (
    <div className="pt-4">
      <DeploymentProvidersView
        providers={providers}
        deploymentRows={deploymentRows}
        selectedProviderId={selectedProviderId}
        onSelectProvider={onSelectProvider}
        onConfigureProvider={onConfigureProvider}
        selectedProviderDeploymentCount={selectedProviderDeploymentCount}
        isLoadingDeployments={isLoadingDeployments}
        isLoadingProviders={isLoadingProviders}
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={onPageChange}
        onCreateDeployment={onCreateDeployment}
        activeSubTab={activeSubTab}
        onTestAgent={onTestAgent}
      />
    </div>
  );
};
