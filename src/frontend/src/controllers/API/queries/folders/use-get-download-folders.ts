import { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IGetDownloadFolders {
  folderId: string;
}

export const useGetDownloadFolders: useMutationFunctionType<
  undefined,
  IGetDownloadFolders
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const downloadFoldersFn = async (
    data: IGetDownloadFolders,
  ): Promise<void> => {
    const res = await api.get(`${getURL("FOLDERS")}/download/${data.folderId}`);
    return res.data;
  };

  const mutation = mutate(
    ["useGetDownloadFolders"],
    downloadFoldersFn,
    options,
  );
  return mutation;
};
