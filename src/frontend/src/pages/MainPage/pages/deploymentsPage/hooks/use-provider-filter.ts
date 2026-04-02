import { useEffect, useMemo, useState } from "react";
import type { ProviderAccount } from "../types";

const ALL_PROVIDERS = "all";

interface ProviderFilter {
  selectedProviderId: string;
  setSelectedProviderId: (id: string) => void;
  providerIdsToQuery: string[];
  providerMap: Record<string, string>;
}

export function useProviderFilter(
  providers: ProviderAccount[],
): ProviderFilter {
  const [selectedProviderId, setSelectedProviderId] = useState(ALL_PROVIDERS);

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

  const providerIdsToQuery = useMemo(() => {
    if (selectedProviderId !== ALL_PROVIDERS) return [selectedProviderId];
    return providers.map((p) => p.id);
  }, [selectedProviderId, providers]);

  const providerMap = useMemo(
    () =>
      Object.fromEntries(providers.map((p) => [p.id, p.name])) as Record<
        string,
        string
      >,
    [providers],
  );

  return {
    selectedProviderId,
    setSelectedProviderId,
    providerIdsToQuery,
    providerMap,
  };
}

export { ALL_PROVIDERS };
