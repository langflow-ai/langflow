import {
  type DeploymentProvider,
  useGetDeploymentProviders,
} from "@/controllers/API/queries/deployments/use-deployments";
import { useEffect, useMemo, useState } from "react";

export const useProviders = () => {
  const [selectedProviderId, setSelectedProviderId] = useState<string | null>(
    null,
  );
  const [registerProviderOpen, setRegisterProviderOpen] = useState(false);
  const [configureProviderOpen, setConfigureProviderOpen] = useState(false);
  const [providerToConfigure, setProviderToConfigure] =
    useState<DeploymentProvider | null>(null);

  const providersQuery = useGetDeploymentProviders({
    refetchOnWindowFocus: false,
  });
  const providers = providersQuery.data?.providers || [];
  const hasProviders = providers.length > 0;

  useEffect(() => {
    const selectedStillExists = selectedProviderId
      ? providers.some((provider) => provider.id === selectedProviderId)
      : false;

    if ((!selectedProviderId || !selectedStillExists) && providers.length > 0) {
      setSelectedProviderId(providers[0].id);
    }
    if (providers.length === 0) {
      setSelectedProviderId(null);
    }
  }, [providers, selectedProviderId]);

  const providerId = selectedProviderId || providers[0]?.id || "";
  const selectedProvider = useMemo(
    () => providers.find((provider) => provider.id === providerId) || null,
    [providers, providerId],
  );

  const handleConfigureProvider = (provider: DeploymentProvider) => {
    setProviderToConfigure(provider);
    setConfigureProviderOpen(true);
  };

  return {
    providers,
    providerId,
    selectedProvider,
    selectedProviderId,
    setSelectedProviderId,
    hasProviders,
    providersQuery,
    registerProviderOpen,
    setRegisterProviderOpen,
    configureProviderOpen,
    setConfigureProviderOpen,
    providerToConfigure,
    setProviderToConfigure,
    handleConfigureProvider,
  };
};
