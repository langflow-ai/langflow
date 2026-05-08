import { useState } from "react";
import { useParams } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useGetProviderAccounts } from "@/controllers/API/queries/deployment-provider-accounts/use-get-provider-accounts";
import { useGetDeploymentsByProviders } from "@/controllers/API/queries/deployments/use-get-deployments-by-providers";
import { useFolderStore } from "@/stores/foldersStore";
import DeploymentsContent from "./components/deployments-content";
import ProvidersContent from "./components/providers-content";
import SubTabToggle, {
  type DeploymentSubTab,
} from "./components/sub-tab-toggle";
import { useProviderFilter } from "./hooks/use-provider-filter";
import type { ProviderAccount } from "./types";

function EnvironmentPickerRow({
  providers,
  selectedProviderId,
  onSelect,
}: {
  providers: ProviderAccount[];
  selectedProviderId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="flex shrink-0 flex-wrap items-center justify-center gap-2">
      <span className="shrink-0 text-sm text-muted-foreground">
        Environment:
      </span>
      <Select value={selectedProviderId} onValueChange={onSelect}>
        <SelectTrigger className="w-[220px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {providers.map((p) => (
            <SelectItem key={p.id} value={p.id}>
              {p.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

export default function DeploymentsPage() {
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const currentFolderId = folderId ?? myCollectionId ?? undefined;

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
    useGetDeploymentsByProviders(providerIdsToQuery, currentFolderId);

  const showEnvironmentToolbar = providers.length > 1 && !isLoadingProviders;

  const showHeaderButton =
    activeSubTab === "providers"
      ? !isLoadingProviders && providers.length > 0
      : !isLoadingProviders && !isLoadingDeployments && deployments.length > 0;

  return (
    <div className="flex flex-col gap-4 pt-4">
      <div className="flex min-h-10 items-center justify-between">
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

      {providers.length > 1 && activeSubTab === "providers" && (
        <div
          className="flex h-8 min-h-8 shrink-0 items-center gap-2"
          data-testid="deployments-shared-toolbar"
        >
          <p className="min-w-0 flex-1 truncate text-sm text-muted-foreground">
            These environments are used when you create or run deployments.
          </p>
        </div>
      )}

      {showEnvironmentToolbar && activeSubTab === "deployments" && (
        <div
          className="flex h-8 min-h-8 shrink-0 items-center gap-2"
          data-testid="deployments-environment-toolbar"
        >
          <EnvironmentPickerRow
            providers={providers}
            selectedProviderId={selectedProviderId}
            onSelect={setSelectedProviderId}
          />
        </div>
      )}

      {activeSubTab === "deployments" && (
        <DeploymentsContent
          providers={providers}
          deployments={deployments}
          isLoading={isLoadingProviders || isLoadingDeployments}
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
