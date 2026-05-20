import type {
  Trigger,
  TriggerUpdate,
} from "@/pages/MainPage/pages/triggersPage/types";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface PatchTriggerParams {
  trigger_id: string;
  patch: TriggerUpdate;
}

export const usePatchTrigger: useMutationFunctionType<
  undefined,
  PatchTriggerParams,
  Trigger
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const fn = async ({
    trigger_id,
    patch,
  }: PatchTriggerParams): Promise<Trigger> => {
    const { data } = await api.patch<Trigger>(
      `${getURL("TRIGGERS")}/${trigger_id}`,
      patch,
    );
    return data;
  };

  return mutate(["usePatchTrigger"], fn, {
    ...options,
    onSuccess: (...args) => {
      queryClient.refetchQueries({ queryKey: ["useGetTriggers"] });
      queryClient.refetchQueries({ queryKey: ["useGetTrigger"] });
      options?.onSuccess?.(...args);
    },
  });
};
