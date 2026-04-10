import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useGetProviderAccounts } from "@/controllers/API/queries/deployment-provider-accounts/use-get-provider-accounts";
import { useGetDeploymentsByProviders } from "@/controllers/API/queries/deployments/use-get-deployments-by-providers";
import DeploymentsContent from "./components/deployments-content";
import ProvidersContent from "./components/providers-content";
import SubTabToggle, {
  type DeploymentSubTab,
} from "./components/sub-tab-toggle";
import { useProviderFilter } from "./hooks/use-provider-filter";

export default function DeploymentsPage() {
  const [activeSubTab, setActiveSubTab] =
    useState<DeploymentSubTab>("deployments");
  const [stepperOpen, setStepperOpen] = useState(false);
  const [addProviderOpen, setAddProviderOpen] = useState(false);

  const { data: providersData, isLoading: isLoadingProviders } =
    useGetProviderAccounts({});
  const providers = providersData?.provider_accounts ?? [];

  const {
    selectedProviderId,
    setSelectedProviderId,
    providerIdsToQuery,
    providerMap,
  } = useProviderFilter(providers);

  const { deployments, isLoading: isLoadingDeployments } =
    useGetDeploymentsByProviders(providerIdsToQuery);

  const showHeaderButton =
    activeSubTab === "providers"
      ? !isLoadingProviders && providers.length > 0
      : !isLoadingProviders && !isLoadingDeployments && deployments.length > 0;

  return (
    <div className="flex flex-col gap-4 pt-4">
      <div className="flex items-center justify-between">
        <SubTabToggle activeTab={activeSubTab} onTabChange={setActiveSubTab} />
        {showHeaderButton && (
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
            {activeSubTab === "providers"
              ? "New Environment"
              : "New Deployment"}
          </Button>
        )}
      </div>

      {activeSubTab === "deployments" && (
        <DeploymentsContent
          providers={providers}
          deployments={deployments}
          isLoading={isLoadingProviders || isLoadingDeployments}
          selectedProviderId={selectedProviderId}
          setSelectedProviderId={setSelectedProviderId}
          providerMap={providerMap}
          stepperOpen={stepperOpen}
          setStepperOpen={setStepperOpen}
        />
      )}

      {activeSubTab === "providers" && (
        <ProvidersContent
          isLoading={isLoadingProviders}
          providers={providers}
          addProviderOpen={addProviderOpen}
          setAddProviderOpen={setAddProviderOpen}
        />
      )}
    </div>
  );
}
