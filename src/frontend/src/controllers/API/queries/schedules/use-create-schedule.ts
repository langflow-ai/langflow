import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type {
  FlowScheduleCreateType,
  FlowScheduleType,
} from "@/types/schedule";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useCreateSchedule: useMutationFunctionType<
  undefined,
  FlowScheduleCreateType
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const createScheduleFn = async (
    payload: FlowScheduleCreateType,
  ): Promise<FlowScheduleType> => {
    const response = await api.post<FlowScheduleType>(
      getURL("SCHEDULES"),
      payload,
    );
    return response.data;
  };

  const mutation: UseMutationResult<
    FlowScheduleType,
    any,
    FlowScheduleCreateType
  > = mutate(["useCreateSchedule"], createScheduleFn, {
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
