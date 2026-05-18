import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { DeploymentListResponse } from "./use-get-deployments";

interface CheckAgentNamesResponse {
  existing_names: string[];
}

interface CheckAgentNamesParams {
  providerId: string;
  names: string[];
}

export const useCheckAgentNames: useQueryFunctionType<
  CheckAgentNamesParams,
  CheckAgentNamesResponse
> = ({ providerId, names }, options) => {
  const { query } = UseRequestProcessor();

  const fn = async (): Promise<CheckAgentNamesResponse> => {
    // Check both DB and provider for existing agent names
    const [dbRes, providerRes] = await Promise.allSettled([
      api.get<DeploymentListResponse>(
        `${getURL("DEPLOYMENTS")}?load_from_provider=false`,
        {
          params: {
            provider_id: providerId,
            names,
            size: 50,
          },
          paramsSerializer: { indexes: null },
        },
      ),
      api.get<DeploymentListResponse>(
        `${getURL("DEPLOYMENTS")}?load_from_provider=true`,
        {
          params: {
            provider_id: providerId,
            names,
            size: 50,
          },
          paramsSerializer: { indexes: null },
        },
      ),
    ]);

    const dbResData = dbRes.status === "fulfilled" ? dbRes.value?.data : null;
    const dbDeployments =
      dbResData?.deployments || dbResData?.provider_data?.deployments || [];
    const dbNames = dbDeployments
      .map(
        (d: { name?: string; display_name?: string }) =>
          d.name || d.display_name,
      )
      .filter(Boolean);

    const providerResData =
      providerRes.status === "fulfilled" ? providerRes.value?.data : null;
    const providerDeployments =
      providerResData?.deployments ||
      providerResData?.provider_data?.deployments ||
      [];

    const providerNames = providerDeployments
      .map(
        (d: { name?: string; display_name?: string }) =>
          d.name || d.display_name,
      )
      .filter(Boolean);

    // Combine and deduplicate
    const existingNames = Array.from(new Set([...dbNames, ...providerNames]));

    return { existing_names: existingNames };
  };

  const sortedNames = [...names].sort();
  return query(
    ["useCheckAgentNames", { providerId, names: sortedNames }],
    fn,
    options,
  );
};
