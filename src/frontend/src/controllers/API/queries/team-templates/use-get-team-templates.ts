import type { useQueryFunctionType } from "@/types/api";
import type { TeamTemplateList } from "@/types/templates/types";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface TeamTemplateListParams {
  page?: number;
  page_size?: number;
  category?: string;
  q?: string;
}

export const useGetTeamTemplates: useQueryFunctionType<
  TeamTemplateListParams,
  TeamTemplateList
> = (params, options?) => {
  const { query } = UseRequestProcessor();
  const getTeamTemplates = async (): Promise<TeamTemplateList> => {
    const response = await api.get<TeamTemplateList>(getURL("TEAM_TEMPLATES"), {
      params,
    });
    return response.data;
  };
  return query(["useGetTeamTemplates", params], getTeamTemplates, {
    refetchOnWindowFocus: false,
    ...options,
  });
};
