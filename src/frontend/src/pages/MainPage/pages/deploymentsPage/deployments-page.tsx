import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useDeleteProviderAccount } from "@/controllers/API/queries/deployment-provider-accounts/use-delete-provider-account";
import { useGetProviderAccounts } from "@/controllers/API/queries/deployment-provider-accounts/use-get-provider-accounts";
import { useDeleteDeployment } from "@/controllers/API/queries/deployments/use-delete-deployment";
import { useGetDeploymentsByProviders } from "@/controllers/API/queries/deployments/use-get-deployments-by-providers";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import AddProviderModal from "./components/add-provider-modal";
import DeploymentStepperModal from "./components/deployment-stepper-modal";
import DeploymentsContent from "./components/deployments-content";
import ProvidersContent from "./components/providers-content";
import SubTabToggle, {
  type DeploymentSubTab,
} from "./components/sub-tab-toggle";
import TestDeploymentModal from "./components/test-deployment-modal/test-deployment-modal";
import { useErrorAlert } from "./hooks/use-error-alert";
import type { Deployment, ProviderAccount } from "./types";

const ALL_PROVIDERS = "all";

export default function DeploymentsPage() {
  const [activeSubTab, setActiveSubTab] =
    useState<DeploymentSubTab>("deployments");
  const [selectedProviderId, setSelectedProviderId] = useState(ALL_PROVIDERS);
  const [stepperOpen, setStepperOpen] = useState(false);
  const [addProviderOpen, setAddProviderOpen] = useState(false);
  const [testTarget, setTestTarget] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [testProviderId, setTestProviderId] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<Deployment | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteProviderTarget, setDeleteProviderTarget] =
    useState<ProviderAccount | null>(null);
  const [deletingProviderId, setDeletingProviderId] = useState<string | null>(
    null,
  );

  const location = useLocation();
  const navigate = useNavigate();
  const showError = useErrorAlert();

  // Auto-open test modal when navigated from canvas deploy button
  useEffect(() => {
    const state = location.state as {
      testDeployment?: { id: string; name: string };
      testProviderId?: string;
    } | null;
    if (state?.testDeployment && state?.testProviderId) {
      setTestTarget(state.testDeployment);
      setTestProviderId(state.testProviderId);
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location.state, location.pathname, navigate]);

  const { data: providersData, isLoading: isLoadingProviders } =
    useGetProviderAccounts({});
  const providers = providersData?.providers ?? [];

  // Build provider id -> name lookup
  const providerMap = useMemo(
    () =>
      Object.fromEntries(providers.map((p) => [p.id, p.name])) as Record<
        string,
        string
      >,
    [providers],
  );

  // Determine which provider IDs to query
  const providerIdsToQuery = useMemo(() => {
    if (selectedProviderId !== ALL_PROVIDERS) return [selectedProviderId];
    return providers.map((p) => p.id);
  }, [selectedProviderId, providers]);

  // Reset filter when the selected provider no longer exists
  useEffect(() => {
    if (
      selectedProviderId !== ALL_PROVIDERS &&
      providers.length > 0 &&
      !providers.some((p) => p.id === selectedProviderId)
    ) {
      setSelectedProviderId(ALL_PROVIDERS);
    }
  }, [providers, selectedProviderId]);

  // Fetch deployments for each selected provider in parallel
  const { deployments, isLoading: isLoadingDeployments } =
    useGetDeploymentsByProviders(providerIdsToQuery);

  const hasProviders = providers.length > 0;
  const isEmpty = !hasProviders || deployments.length === 0;

  const { mutate: deleteDeployment } = useDeleteDeployment();
  const { mutate: deleteProviderAccount } = useDeleteProviderAccount();

  const handleConfirmDelete = useCallback(
    (e: React.MouseEvent<HTMLButtonElement, MouseEvent>) => {
      e.stopPropagation();
      if (!deleteTarget) return;
      const target = deleteTarget;
      setDeletingId(target.id);
      setDeleteTarget(null);
      deleteDeployment(
        { deployment_id: target.id },
        {
          onError: (error: unknown) => {
            showError("Error deleting deployment", error);
          },
          onSettled: () => setDeletingId(null),
        },
      );
    },
    [deleteTarget, deleteDeployment, showError],
  );

  const handleConfirmDeleteProvider = useCallback(
    (e: React.MouseEvent<HTMLButtonElement, MouseEvent>) => {
      e.stopPropagation();
      if (!deleteProviderTarget) return;
      const target = deleteProviderTarget;
      setDeletingProviderId(target.id);
      setDeleteProviderTarget(null);
      deleteProviderAccount(
        { provider_id: target.id },
        {
          onError: (error: unknown) => {
            showError("Error deleting environment", error);
          },
          onSettled: () => setDeletingProviderId(null),
        },
      );
    },
    [deleteProviderTarget, deleteProviderAccount, showError],
  );

  const handleTestDeployment = useCallback((deployment: Deployment) => {
    setTestTarget(deployment);
    setTestProviderId(deployment.provider_account_id ?? "");
  }, []);

  const handleTestFromStepper = useCallback(
    (deployment: { id: string; name: string }, providerId: string) => {
      setTestTarget(deployment);
      setTestProviderId(providerId);
    },
    [],
  );

  return (
    <div className="flex flex-col gap-4 pt-4">
      <div className="flex items-center justify-between">
        <SubTabToggle activeTab={activeSubTab} onTabChange={setActiveSubTab} />
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
          {activeSubTab === "providers" ? "New Environment" : "New Deployment"}
        </Button>
      </div>

      {activeSubTab === "deployments" && (
        <>
          {providers.length > 1 && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">
                Environment:
              </span>
              <Select
                value={selectedProviderId}
                onValueChange={setSelectedProviderId}
              >
                <SelectTrigger className="w-[220px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL_PROVIDERS}>
                    All environments
                  </SelectItem>
                  {providers.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          <DeploymentsContent
            isLoading={isLoadingProviders || isLoadingDeployments}
            isEmpty={isEmpty}
            deployments={deployments}
            providerMap={providerMap}
            deletingId={deletingId}
            onCreateDeployment={() => setStepperOpen(true)}
            onTestDeployment={handleTestDeployment}
            onDeleteDeployment={setDeleteTarget}
          />
        </>
      )}

      {activeSubTab === "providers" && (
        <ProvidersContent
          isLoading={isLoadingProviders}
          providers={providers}
          deletingId={deletingProviderId}
          onAddProvider={() => setAddProviderOpen(true)}
          onDeleteProvider={setDeleteProviderTarget}
        />
      )}

      <DeploymentStepperModal
        open={stepperOpen}
        setOpen={setStepperOpen}
        onTestDeployment={handleTestFromStepper}
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

      <AddProviderModal open={addProviderOpen} setOpen={setAddProviderOpen} />

      <DeleteConfirmationModal
        open={!!deleteProviderTarget}
        setOpen={(open) => {
          if (!open) setDeleteProviderTarget(null);
        }}
        description={`environment "${deleteProviderTarget?.name}"`}
        onConfirm={handleConfirmDeleteProvider}
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
