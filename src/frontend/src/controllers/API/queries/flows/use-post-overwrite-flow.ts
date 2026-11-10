import type { UseMutationResult } from "@tanstack/react-query";
import type { ReactFlowJsonObject } from "@xyflow/react";
import type { AxiosError } from "axios";
import { refetchQueriesFresh } from "@/controllers/API/helpers/query-cache";
import type { useMutationFunctionType } from "@/types/api";
import type { FlowType } from "@/types/flow";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostOverwriteFlow {
  id: string;
  data: ReactFlowJsonObject;
  /** The version the person reviewed in the dialog, not the one they were refused on. */
  reviewedVersionToken: string;
}

/**
 * Replaces a flow with a merged graph, archiving the version it replaced.
 *
 * The precondition is deliberately still sent. Overwriting means "replace what I
 * just reviewed", not "write regardless": a third person who saved while the
 * dialog was open would otherwise be discarded without anyone being told, which
 * is the same lost update the conflict banner exists to prevent.
 */
export const usePostOverwriteFlow: useMutationFunctionType<
  undefined,
  IPostOverwriteFlow,
  FlowType,
  AxiosError
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const postOverwriteFlowFn = async ({
    id,
    data,
    reviewedVersionToken,
  }: IPostOverwriteFlow): Promise<FlowType> => {
    const response = await api.post<FlowType>(
      `${getURL("FLOWS")}/${id}/overwrite`,
      { data },
      { headers: { "If-Match": reviewedVersionToken } },
    );
    return response.data;
  };

  const mutation: UseMutationResult<FlowType, AxiosError, IPostOverwriteFlow> =
    mutate(["usePostOverwriteFlow"], postOverwriteFlowFn, {
      ...options,
      onSettled: (response) => {
        if (response) {
          // The archived version is only useful if the history panel shows it.
          void refetchQueriesFresh(queryClient, {
            queryKey: ["useGetFlowVersions", { flowId: response.id }],
          });
        }
      },
    });

  return mutation;
};

export default usePostOverwriteFlow;
