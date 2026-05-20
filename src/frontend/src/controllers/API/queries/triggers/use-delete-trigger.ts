import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteTriggerParams {
  trigger_id: string;
}

export const useDeleteTrigger: useMutationFunctionType<
  undefined,
  DeleteTriggerParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const fn = async ({ trigger_id }: DeleteTriggerParams) => {
    await api.delete(`${getURL("TRIGGERS")}/${trigger_id}`);
  };

  return mutate(["useDeleteTrigger"], fn, {
    ...options,
    onSuccess: (...args) => {
      queryClient.refetchQueries({ queryKey: ["useGetTriggers"] });
      options?.onSuccess?.(...args);
    },
  });
};
