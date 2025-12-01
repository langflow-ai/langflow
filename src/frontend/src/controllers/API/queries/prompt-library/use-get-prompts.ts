import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import type { ApiResponse, PromptsListResponse } from "./types";

interface GetPromptsParams {
  skip?: number;
  limit?: number;
  status?: string;
  name?: string;
  tags?: string;
}

export const useGetPrompts = (params?: GetPromptsParams) => {
  const queryParams = new URLSearchParams();
  if (params?.skip !== undefined) queryParams.append("skip", params.skip.toString());
  if (params?.limit !== undefined) queryParams.append("limit", params.limit.toString());
  if (params?.status) queryParams.append("status", params.status);
  if (params?.name) queryParams.append("name", params.name);
  if (params?.tags) queryParams.append("tags", params.tags);

  const queryString = queryParams.toString();
  const url = `${getURL("PROMPT_LIBRARY")}/prompts/versions${queryString ? `?${queryString}` : ""}`;

  return useQuery({
    queryKey: ["useGetPrompts", params],
    queryFn: async () => {
      const response = await api.get<ApiResponse<PromptsListResponse>>(url);
      return response.data.data;
    },
  });
};
