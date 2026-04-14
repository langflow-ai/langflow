import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface SnapshotListResponse {
  provider_data?: {
    tools?: Array<{ id: string; name: string }>;
    total?: number;
  };
}

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
    const { data } = await api.get<SnapshotListResponse>(
      `${getURL("DEPLOYMENTS")}/snapshots`,
      {
        params: {
          provider_id: providerId,
          names,
          size: 50,
        },
        paramsSerializer: { indexes: null },
      },
    );
    const existingNames = (data.provider_data?.tools ?? [])
      .map((t) => t.name)
      .filter(Boolean);
    return { existing_names: existingNames };
  };

  const sortedNames = [...names].sort();
  return query(
    ["useCheckToolNames", { providerId, names: sortedNames }],
    fn,
    options,
  );
};
