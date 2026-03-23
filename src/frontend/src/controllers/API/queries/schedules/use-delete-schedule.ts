import type { UseMutationResult } from "@tanstack/react-query";
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

  const deleteScheduleFn = async ({
    id,
    flow_id,
  }: IDeleteSchedule): Promise<void> => {
    await api.delete(`${getURL("SCHEDULES")}/${id}`);
  };

  const mutation: UseMutationResult<void, any, IDeleteSchedule> = mutate(
    ["useDeleteSchedule"],
    deleteScheduleFn,
    {
      onSettled: (_res, _err, variables) => {
        if (variables) {
          queryClient.invalidateQueries({
            queryKey: ["useGetSchedule", variables.flow_id],
          });
        }
      },
      ...options,
    },
  );

  return mutation;
};
