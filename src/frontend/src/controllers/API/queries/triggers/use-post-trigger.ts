import type {
  Trigger,
  TriggerCreate,
} from "@/pages/MainPage/pages/triggersPage/types";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const usePostTrigger: useMutationFunctionType<
  undefined,
  TriggerCreate,
  Trigger
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const fn = async (payload: TriggerCreate): Promise<Trigger> => {
    const { data } = await api.post<Trigger>(`${getURL("TRIGGERS")}`, payload);
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
