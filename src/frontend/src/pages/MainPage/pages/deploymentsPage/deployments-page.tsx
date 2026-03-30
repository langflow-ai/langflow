import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useGetProviderAccounts } from "@/controllers/API/queries/deployment-provider-accounts";
import { useGetDeployments } from "@/controllers/API/queries/deployments";
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
  const [testTarget, setTestTarget] = useState<Deployment | null>(null);

  const { data: providersData } = useGetProviderAccounts({});
  const providers = providersData?.providers ?? [];
  const firstProviderId = providers[0]?.id ?? "";

  const { data, isLoading } = useGetDeployments(
    { provider_id: firstProviderId },
    { enabled: !!firstProviderId },
  );
  const deployments = data?.deployments ?? [];
  const isEmpty = !firstProviderId || deployments.length === 0;

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
          onCreateDeployment={() => setStepperOpen(true)}
          onTestDeployment={setTestTarget}
        />
      )}

      {activeSubTab === "providers" && (
        <div className="py-24 text-center text-sm text-muted-foreground">
          Deployment Providers coming soon
        </div>
      )}

      <DeploymentStepperModal open={stepperOpen} setOpen={setStepperOpen} />

      <TestDeploymentModal
        open={!!testTarget}
        setOpen={(open) => {
          if (!open) setTestTarget(null);
        }}
        deployment={testTarget}
        providerId={firstProviderId}
      />
    </div>
  );
}
