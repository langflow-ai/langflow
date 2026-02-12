import type { useMutationFunctionType } from "@/types/api";
import type {
  FlowScheduleCreateType,
  FlowScheduleType,
} from "@/types/schedules";
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
    const response = await api.post(getURL("SCHEDULES"), payload);
    return response.data;
  };

  return mutate(["useCreateSchedule"], createScheduleFn, {
    onSettled: (_data, _error, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["useGetSchedules", variables.flow_id],
      });
    },
    ...options,
  });
};
