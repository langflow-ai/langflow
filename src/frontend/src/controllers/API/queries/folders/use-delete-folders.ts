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
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteFolder = async ({
    folder_id,
  }: DeleteFoldersParams): Promise<any> => {
    const res = await api.delete(`${getURL("FOLDERS")}/${folder_id}`);
    // returning id to use it in onSuccess and delete the folder from the cache
    return folder_id;
  };

  const mutation: UseMutationResult<
    DeleteFoldersParams,
    any,
    DeleteFoldersParams
  > = mutate(["useDeleteFolders"], deleteFolder, {
    ...options,
    onSettled: () => {
      queryClient.refetchQueries({ queryKey: ["useGetFolders"] });
    },
    onSuccess: (id) => {
      queryClient.removeQueries({
        queryKey: ["useGetFolder", { id }],
        exact: true,
      });
    },
  });

  return mutation;
};
