import type { UseMutationResult } from "@tanstack/react-query";
import { useFolderStore } from "@/stores/foldersStore";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteFoldersParams {
  folder_id: string;
  edit_revision: number;
}

export const useDeleteFolders: useMutationFunctionType<
  undefined,
  DeleteFoldersParams,
  string,
  unknown
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();
  const setFolders = useFolderStore((state) => state.setFolders);
  const folders = useFolderStore((state) => state.folders);

  const deleteFolder = async ({
    folder_id,
    edit_revision,
  }: DeleteFoldersParams): Promise<string> => {
    await api.delete(`${getURL("PROJECTS")}/${folder_id}`, {
      headers: { "If-Match": `"project:${folder_id}:${edit_revision}"` },
    });
    setFolders(folders.filter((f) => f.id !== folder_id));
    return folder_id;
  };

  const mutation: UseMutationResult<string, unknown, DeleteFoldersParams> =
    mutate(["useDeleteFolders"], deleteFolder, {
      ...options,
      onSettled: (id) => {
        queryClient.refetchQueries({ queryKey: ["useGetFolders", id] });
        queryClient.invalidateQueries({ queryKey: ["useGetFolders"] });
      },
    });

  return mutation;
};
