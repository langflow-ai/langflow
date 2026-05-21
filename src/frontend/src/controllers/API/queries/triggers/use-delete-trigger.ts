import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteTriggerParams {
  flow_id: string;
  component_id: string;
}

export const useDeleteTrigger: useMutationFunctionType<
  undefined,
  DeleteTriggerParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const fn = async ({ flow_id, component_id }: DeleteTriggerParams) => {
    await api.delete(
      `${getURL("TRIGGERS")}/${flow_id}/${encodeURIComponent(component_id)}`,
    );
  };

  return mutate(["useDeleteTrigger"], fn, {
    ...options,
    onSuccess: (...args) => {
      queryClient.refetchQueries({ queryKey: ["useGetTriggers"] });
      options?.onSuccess?.(...args);
    },
  });
};
