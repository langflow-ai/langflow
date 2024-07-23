import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useFolderStore } from "@/stores/foldersStore";
import { Users, useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostAddUploadFolders {
  formData: FormData;
}

export const usePostUploadFolders: useMutationFunctionType<
  undefined,
  IPostAddUploadFolders
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const uploadFoldersFn = async (
    payload: IPostAddUploadFolders,
  ): Promise<void> => {
    const res = await api.post(
      `${getURL("FOLDERS")}/upload/`,
      payload.formData,
    );
    await useFolderStore.getState().getFoldersApi(true);
    return res.data;
  };

  const mutation = mutate(["usePostUploadFolders"], uploadFoldersFn, options);

  return mutation;
};
