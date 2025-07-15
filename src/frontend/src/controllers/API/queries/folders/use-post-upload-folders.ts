import type { useMutationFunctionType } from "@/types/api";
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
  const { mutate, queryClient } = UseRequestProcessor();

  const uploadFoldersFn = async (
    payload: IPostAddUploadFolders,
  ): Promise<void> => {
    const res = await api.post(
      `${getURL("PROJECTS")}/upload/`,
      payload.formData,
    );
    return res.data;
  };

  const mutation = mutate(["usePostUploadFolders"], uploadFoldersFn, {
    ...options,
    onSettled: () => {
      queryClient.refetchQueries({ queryKey: ["useGetFolders"] });
    },
  });

  return mutation;
};
