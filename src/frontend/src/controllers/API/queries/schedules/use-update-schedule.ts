import type { useMutationFunctionType } from "@/types/api";
import type { FlowScheduleType, FlowScheduleUpdateType } from "@/types/schedules";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IUpdateSchedule extends FlowScheduleUpdateType {
  id: string;
  flow_id: string;
}

export const useUpdateSchedule: useMutationFunctionType<
  undefined,
  IUpdateSchedule
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const updateScheduleFn = async ({
    id,
    flow_id,
    ...payload
  }: IUpdateSchedule): Promise<FlowScheduleType> => {
    const response = await api.patch(
      `${getURL("SCHEDULES")}/${id}`,
      payload,
    );
    return response.data;
  };

  return mutate(["useUpdateSchedule"], updateScheduleFn, {
    onSettled: (_data, _error, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["useGetSchedules", variables.flow_id],
      });
    },
    ...options,
  });
};
