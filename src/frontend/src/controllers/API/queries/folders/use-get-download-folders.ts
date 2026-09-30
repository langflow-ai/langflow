import type { UseMutationResult } from "@tanstack/react-query";
import { customGetDownloadTypeFolders } from "@/customization/utils/custom-get-download-folders";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IGetDownloadFolders {
  folderId: string;
}

export const useGetDownloadFolders: useMutationFunctionType<
  any, // Changed to any since we're getting the full response
  IGetDownloadFolders
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const downloadFoldersFn = async (
    payload: IGetDownloadFolders,
  ): Promise<any> => {
    const response = await api.get<any>(
      `${getURL("PROJECTS")}/download/${payload.folderId}`,
      customGetDownloadTypeFolders(),
    );
    return response;
  };

  const mutation: UseMutationResult<any, any, IGetDownloadFolders> = mutate(
    ["useGetDownloadFolders"],
    downloadFoldersFn,
    options,
  );

  return mutation;
};
