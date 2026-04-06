import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type { FlowScheduleType } from "@/types/schedule";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IToggleSchedule {
  id: string;
  flow_id: string;
}

export const useToggleSchedule: useMutationFunctionType<
  undefined,
  IToggleSchedule
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const toggleScheduleFn = async ({
    id,
  }: IToggleSchedule): Promise<FlowScheduleType> => {
    const response = await api.patch<FlowScheduleType>(
      `${getURL("SCHEDULES")}/${id}/toggle`,
    );
    return response.data;
  };

  const mutation: UseMutationResult<FlowScheduleType, any, IToggleSchedule> =
    mutate(["useToggleSchedule"], toggleScheduleFn, {
      onSettled: (res, _err, variables) => {
        if (variables) {
          queryClient.invalidateQueries({
            queryKey: ["useGetSchedule", variables.flow_id],
          });
        }
      },
      ...options,
    });

  return mutation;
};
