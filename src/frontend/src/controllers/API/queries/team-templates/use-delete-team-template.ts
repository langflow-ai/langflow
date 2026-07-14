import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useDeleteTeamTemplate: useMutationFunctionType<
  undefined,
  string,
  void
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteTeamTemplate = async (id: string): Promise<void> => {
    await api.delete(`${getURL("TEAM_TEMPLATES")}/${id}`);
  };

  return mutate(["useDeleteTeamTemplate"], deleteTeamTemplate, {
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["useGetTeamTemplates"] });
    },
    ...options,
  });
};
