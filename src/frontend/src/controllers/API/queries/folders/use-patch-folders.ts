import { AddFolderType } from "@/pages/MainPage/entities";
import { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPatchPatchFolders {
  data: AddFolderType;
  folderId: string;
}

export const usePatchFolders: useMutationFunctionType<
  undefined,
  IPatchPatchFolders
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const patchFoldersFn = async (
    newFolder: IPatchPatchFolders,
  ): Promise<void> => {
    const payload = {
      name: newFolder.data.name,
      description: newFolder.data.description,
      flows_list: newFolder.data.flows ?? [],
      components_list: newFolder.data.components ?? [],
    };

    const res = await api.patch(
      `${getURL("PROJECTS")}/${newFolder.folderId}`,
      payload,
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
