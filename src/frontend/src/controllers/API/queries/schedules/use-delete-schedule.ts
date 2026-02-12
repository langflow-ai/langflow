import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IDeleteSchedule {
  id: string;
  flow_id: string;
}

export const useDeleteSchedule: useMutationFunctionType<
  undefined,
  IDeleteSchedule
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteScheduleFn = async ({ id }: IDeleteSchedule): Promise<void> => {
    await api.delete(`${getURL("SCHEDULES")}/${id}`);
  };

  return mutate(["useDeleteSchedule"], deleteScheduleFn, {
    onSettled: (_data, _error, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["useGetSchedules", variables.flow_id],
      });
    },
    ...options,
  });
};
