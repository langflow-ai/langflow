import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type { FlowScheduleType, FlowScheduleUpdateType } from "@/types/schedule";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IUpdateSchedule extends FlowScheduleUpdateType {
  id: string;
}

export const useUpdateSchedule: useMutationFunctionType<
  undefined,
  IUpdateSchedule
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const updateScheduleFn = async ({
    id,
    ...payload
  }: IUpdateSchedule): Promise<FlowScheduleType> => {
    const response = await api.patch<FlowScheduleType>(
      `${getURL("SCHEDULES")}/${id}`,
      payload,
    );
    return response.data;
  };

  const mutation: UseMutationResult<FlowScheduleType, any, IUpdateSchedule> =
    mutate(["useUpdateSchedule"], updateScheduleFn, {
      onSettled: (res) => {
        if (res) {
          queryClient.invalidateQueries({
            queryKey: ["useGetSchedule", res.flow_id],
          });
        }
      },
      ...options,
    });

  return mutation;
};
