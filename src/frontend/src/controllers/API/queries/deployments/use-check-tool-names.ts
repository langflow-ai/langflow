import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface CheckToolNamesResponse {
  existing_names: string[];
}

interface CheckToolNamesParams {
  providerId: string;
  names: string[];
}

export const useCheckToolNames: useQueryFunctionType<
  CheckToolNamesParams,
  CheckToolNamesResponse
> = ({ providerId, names }, options) => {
  const { query } = UseRequestProcessor();

  const fn = async (): Promise<CheckToolNamesResponse> => {
    const { data } = await api.get<CheckToolNamesResponse>(
      `${getURL("DEPLOYMENTS")}/snapshots/check-names`,
      {
        params: { provider_id: providerId, names },
        paramsSerializer: { indexes: null },
      },
    );
    return data;
  };

  const sortedNames = [...names].sort();
  return query(
    ["useCheckToolNames", { providerId, names: sortedNames }],
    fn,
    options,
  );
};
