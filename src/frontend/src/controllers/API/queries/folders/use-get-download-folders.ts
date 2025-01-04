import { useMutationFunctionType } from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
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
      `${getURL("FOLDERS")}/download/${payload.folderId}`,
      {
        responseType: "blob",
        headers: {
          Accept: "application/x-zip-compressed",
        },
      },
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
