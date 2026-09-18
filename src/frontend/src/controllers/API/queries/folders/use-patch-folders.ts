import type { AddFolderType, FolderType } from "@/pages/MainPage/entities";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPatchPatchFolders {
  data: Pick<AddFolderType, "name" | "description">;
  folderId: string;
  editRevision: number;
}

export const usePatchFolders: useMutationFunctionType<
  undefined,
  IPatchPatchFolders
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const patchFoldersFn = async (
    newFolder: IPatchPatchFolders,
  ): Promise<FolderType> => {
    const payload = {
      name: newFolder.data.name,
      description: newFolder.data.description,
    };

    const res = await api.patch<FolderType>(
      `${getURL("PROJECTS")}/${newFolder.folderId}`,
      payload,
      {
        headers: {
          "If-Match": `"project:${newFolder.folderId}:${newFolder.editRevision}"`,
        },
      },
    );
    return res.data;
  };

  const mutation = mutate(["usePatchFolders"], patchFoldersFn, {
    ...options,
    onSettled: () => {
      queryClient.refetchQueries({ queryKey: ["useGetFolders"] });
    },
  });

  return mutation;
};
