import { useFolderStore } from "@/stores/foldersStore";
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
  const setFolders = useFolderStore((state) => state.setFolders);
  const folders = useFolderStore((state) => state.folders);

  const deleteFolder = async ({
    folder_id,
  }: DeleteFoldersParams): Promise<any> => {
    await api.delete(`${getURL("PROJECTS")}/${folder_id}`);
    setFolders(folders.filter((f) => f.id !== folder_id));
    return folder_id;
  };

  const mutation: UseMutationResult<
    DeleteFoldersParams,
    any,
    DeleteFoldersParams
  > = mutate(["useDeleteFolders"], deleteFolder, {
    ...options,
    onSettled: (id) => {
      queryClient.refetchQueries({ queryKey: ["useGetFolders", id] });
    },
  });

  return mutation;
};
