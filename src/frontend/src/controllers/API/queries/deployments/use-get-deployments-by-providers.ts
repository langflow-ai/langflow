import { useQueries } from "@tanstack/react-query";
import type { Deployment } from "@/pages/MainPage/pages/deploymentsPage/types";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import type { DeploymentListResponse } from "./use-get-deployments";

async function fetchDeployments(
  providerId: string,
  projectId?: string,
): Promise<DeploymentListResponse> {
  const { data } = await api.get<DeploymentListResponse>(
    `${getURL("DEPLOYMENTS")}`,
    {
      params: {
        provider_id: providerId,
        ...(projectId ? { project_id: projectId } : {}),
        page: 1,
        size: 20,
      },
    },
  );
  return data;
}

interface UseGetDeploymentsByProvidersResult {
  deployments: Deployment[];
  isLoading: boolean;
}

export function useGetDeploymentsByProviders(
  providerIds: string[],
  projectId?: string,
): UseGetDeploymentsByProvidersResult {
  return useQueries({
    queries: providerIds.map((pid) => ({
      queryKey: [
        "useGetDeployments",
        {
          provider_id: pid,
          ...(projectId ? { project_id: projectId } : {}),
          page: 1,
          size: 20,
        },
      ],
      queryFn: () => fetchDeployments(pid, projectId),
      enabled: !!pid,
    })),
    combine: (results): UseGetDeploymentsByProvidersResult => {
      const merged: Deployment[] = [];
      for (let i = 0; i < results.length; i++) {
        const result = results[i];
        const pid = providerIds[i];
        const data = result.data;
        if (!data?.deployments || !pid) {
          continue;
        }
        for (const d of data.deployments) {
          merged.push({
            ...d,
            provider_id:
              d.provider_id !== undefined && d.provider_id !== null
                ? String(d.provider_id)
                : String(pid),
          });
        }
      }
      return {
        deployments: merged,
        isLoading: results.some((r) => r.isLoading),
      };
    },
  });
}
