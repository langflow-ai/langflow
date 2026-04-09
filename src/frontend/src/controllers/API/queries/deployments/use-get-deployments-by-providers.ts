import { useQueries } from "@tanstack/react-query";
import type { Deployment } from "@/pages/MainPage/pages/deploymentsPage/types";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import type { DeploymentListResponse } from "./use-get-deployments";

async function fetchDeployments(
  providerId: string,
): Promise<DeploymentListResponse> {
  const { data } = await api.get<DeploymentListResponse>(
    `${getURL("DEPLOYMENTS")}`,
    { params: { provider_id: providerId, page: 1, size: 20 } },
  );
  return data;
}

interface UseGetDeploymentsByProvidersResult {
  deployments: Deployment[];
  isLoading: boolean;
}

export function useGetDeploymentsByProviders(
  providerIds: string[],
): UseGetDeploymentsByProvidersResult {
  return useQueries({
    queries: providerIds.map((pid) => ({
      queryKey: ["useGetDeployments", { provider_id: pid, page: 1, size: 20 }],
      queryFn: () => fetchDeployments(pid),
      enabled: !!pid,
    })),
    combine: (results): UseGetDeploymentsByProvidersResult => {
      const merged: Deployment[] = [];
      for (const result of results) {
        const data = result.data;
        if (data?.deployments) {
          merged.push(...data.deployments);
        }
      }
      return {
        deployments: merged,
        isLoading: results.some((r) => r.isLoading),
      };
    },
  });
}
