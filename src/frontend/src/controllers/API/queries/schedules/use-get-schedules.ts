import type { FlowScheduleType } from "@/types/schedules";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetSchedules = (flowId: string) => {
  const { query } = UseRequestProcessor();

  const getSchedulesFn = async (): Promise<FlowScheduleType[]> => {
    const response = await api.get(`${getURL("SCHEDULES")}?flow_id=${flowId}`);
    return response.data;
  };

  return query(["useGetSchedules", flowId], getSchedulesFn, {
    enabled: !!flowId,
  });
};
