import type { useMutationFunctionType } from "@/types/api";
import type { TeamTemplate } from "@/types/templates/types";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetTeamTemplate: useMutationFunctionType<
  undefined,
  string,
  TeamTemplate
> = (options?) => {
  const { mutate } = UseRequestProcessor();
  const getTeamTemplate = async (id: string): Promise<TeamTemplate> => {
    const response = await api.get<TeamTemplate>(
      `${getURL("TEAM_TEMPLATES")}/${id}`,
    );
    return response.data;
  };
  return mutate(["useGetTeamTemplate"], getTeamTemplate, options);
};
