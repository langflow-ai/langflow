import { useEffect, useMemo, useState } from "react";
import type { ProviderAccount } from "../types";

interface ProviderFilter {
  selectedProviderId: string;
  setSelectedProviderId: (id: string) => void;
  providerIdsToQuery: string[];
  providerMap: Record<string, string>;
}

export function useProviderFilter(
  providers: ProviderAccount[],
): ProviderFilter {
  const [selectedProviderId, setSelectedProviderId] = useState(
    () => providers[0]?.id ?? "",
  );

  // Select first provider once providers load, or reset when selected is removed
  useEffect(() => {
    if (providers.length === 0) return;

    if (
      !selectedProviderId ||
      !providers.some((p) => p.id === selectedProviderId)
    ) {
      setSelectedProviderId(providers[0].id);
    }
  }, [providers, selectedProviderId]);

  const providerIdsToQuery = useMemo(
    () => (selectedProviderId ? [selectedProviderId] : []),
    [selectedProviderId],
  );

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
