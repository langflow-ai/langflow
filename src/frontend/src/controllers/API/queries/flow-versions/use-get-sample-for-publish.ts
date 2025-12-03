import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

export interface SampleForPublishResponse {
  id: string | null;
  flow_version_id: string | null;
  original_flow_id: string;
  version: string | null;
  storage_account: string | null;
  container_name: string | null;
  file_names: string[] | null;
  sample_text: string[] | null;
  sample_output: Record<string, unknown> | null;
}

export const useGetSampleForPublish = (
  flowId: string | undefined,
  version?: string | null
) => {
  return useQuery<SampleForPublishResponse>({
    queryKey: ["sample-for-publish", flowId, version],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (version) {
        params.append("version", version);
      }
      const queryString = params.toString();
      const url = `${getURL("FLOW_VERSIONS")}/flow/${flowId}/sample-for-publish${queryString ? `?${queryString}` : ""}`;
      const response = await api.get(url);
      return response.data;
    },
    enabled: !!flowId,
    staleTime: 0, // Always consider data stale to ensure fresh data
    refetchOnMount: "always", // Refetch when component mounts
    refetchOnWindowFocus: false,
  });
};
