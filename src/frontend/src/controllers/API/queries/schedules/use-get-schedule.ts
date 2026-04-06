import type { UseQueryResult } from "@tanstack/react-query";
import type { FlowScheduleType } from "@/types/schedule";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetSchedule = (
  flowId: string,
  enabled: boolean = true,
): UseQueryResult<FlowScheduleType | null> => {
  const { query } = UseRequestProcessor();

  const getScheduleFn = async (): Promise<FlowScheduleType | null> => {
    try {
      const response = await api.get<FlowScheduleType>(
        `${getURL("SCHEDULES")}/${flowId}`,
      );
      return response.data;
    } catch (error: any) {
      if (error?.response?.status === 404) {
        return null;
      }
      throw error;
    }
  };

  return query(["useGetSchedule", flowId], getScheduleFn, {
    enabled: enabled && !!flowId,
    refetchOnWindowFocus: false,
  });
};
