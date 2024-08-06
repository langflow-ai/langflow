import { useMutationFunctionType } from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostDownloadMultipleFlows {
  flow_ids: string[];
}

export const usePostDownloadMultipleFlows: useMutationFunctionType<
  undefined,
  IPostDownloadMultipleFlows
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const postDownloadMultipleFlowsFn = async (
    payload: IPostDownloadMultipleFlows,
  ): Promise<any> => {
    const response = await api.post<any>(
      `${getURL("FLOWS")}/download/`,
      payload.flow_ids,
      { responseType: "blob" },
    );

    return response.data;
  };

  const mutation: UseMutationResult<
    IPostDownloadMultipleFlows,
    any,
    IPostDownloadMultipleFlows
  > = mutate(
    ["usePostDownloadMultipleFlows"],
    postDownloadMultipleFlowsFn,
    options,
  );

  return mutation;
};
