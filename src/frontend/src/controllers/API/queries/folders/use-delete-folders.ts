import { useMutationFunctionType } from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteFoldersParams {
  folder_id: string;
}

export const useDeleteFolders: useMutationFunctionType<
  undefined,
  DeleteFoldersParams
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const deleteFolder = async ({
    folder_id,
  }: DeleteFoldersParams): Promise<any> => {
    const res = await api.delete(`${getURL("FOLDERS")}/${folder_id}`);
    return res.data;
  };

  const mutation: UseMutationResult<
    DeleteFoldersParams,
    any,
    DeleteFoldersParams
  > = mutate(["useDeleteFolders"], deleteFolder, options);

  return mutation;
};
