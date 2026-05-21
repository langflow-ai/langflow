import type {
  BulkDeleteSummary,
} from "@/pages/MainPage/pages/triggersPage/types";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useDeleteAllTriggers: useMutationFunctionType<
  undefined,
  void,
  BulkDeleteSummary
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const fn = async (): Promise<BulkDeleteSummary> => {
    const { data } = await api.delete<BulkDeleteSummary>(`${getURL("TRIGGERS")}`);
    return data;
  };

  return mutate(["useDeleteAllTriggers"], fn, {
    ...options,
    onSuccess: (...args) => {
      queryClient.refetchQueries({ queryKey: ["useGetTriggers"] });
      options?.onSuccess?.(...args);
    },
  });
};
