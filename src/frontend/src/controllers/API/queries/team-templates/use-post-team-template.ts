import type { useMutationFunctionType } from "@/types/api";
import type {
  CreateTeamTemplatePayload,
  TeamTemplate,
} from "@/types/templates/types";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const usePostTeamTemplate: useMutationFunctionType<
  undefined,
  CreateTeamTemplatePayload,
  TeamTemplate & { cleared_fields: number }
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();
  const postTeamTemplate = async (
    payload: CreateTeamTemplatePayload,
  ): Promise<TeamTemplate & { cleared_fields: number }> => {
    const response = await api.post(getURL("TEAM_TEMPLATES"), payload);
    return response.data;
  };
  return mutate(["usePostTeamTemplate"], postTeamTemplate, {
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["useGetTeamTemplates"] });
    },
    ...options,
  });
};
