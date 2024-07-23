import { AddFolderType } from "@/pages/MainPage/entities";
import { useFolderStore } from "@/stores/foldersStore";
import { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPatchAddFolders {
  data: AddFolderType;
}

export const usePatchFolders: useMutationFunctionType<
  undefined,
  IPatchAddFolders
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const addFoldersFn = async (newFolder: IPatchAddFolders): Promise<void> => {
    const payload = {
      name: newFolder.data.name,
      description: newFolder.data.description,
      flows_list: newFolder.data.flows ?? [],
      components_list: newFolder.data.components ?? [],
    };

    const res = await api.patch(`${getURL("FOLDERS")}/`, payload);
    await useFolderStore.getState().getFoldersApi(true);
    return res.data;
  };

  const mutation = mutate(["usePatchFolders"], addFoldersFn, options);

  return mutation;
};
