import type {
  TriggerInstance,
} from "@/pages/MainPage/pages/triggersPage/types";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

/**
 * Body of POST /api/v1/triggers — mirrors ``TriggerCreateRequest`` on
 * the backend one field at a time so the modal can submit the same
 * shape it edits.
 */
export interface TriggerCreatePayload {
  flow_id: string;
  at_specific_time: boolean;
  interval_value: number;
  interval_unit: "minutes" | "hours";
  time_of_day: string;
  timezone: string;
  max_attempts: number;
}

export const usePostTrigger: useMutationFunctionType<
  undefined,
  TriggerCreatePayload,
  TriggerInstance
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const fn = async (payload: TriggerCreatePayload): Promise<TriggerInstance> => {
    const { data } = await api.post<TriggerInstance>(
      `${getURL("TRIGGERS")}`,
      payload,
    );
    return data;
  };

  return mutate(["usePostTrigger"], fn, {
    ...options,
    onSuccess: (...args) => {
      queryClient.refetchQueries({ queryKey: ["useGetTriggers"] });
      options?.onSuccess?.(...args);
    },
  });
};
