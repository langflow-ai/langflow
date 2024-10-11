import { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostAddUploadFlowToFolder {
  flows: FormData;
  folderId: string;
}

export const usePostUploadFlowToFolder: useMutationFunctionType<
  undefined,
  IPostAddUploadFlowToFolder
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const uploadFlowToFolderFn = async (
    payload: IPostAddUploadFlowToFolder,
  ): Promise<void> => {
    const res = await api.post(
      `${getURL("FLOWS")}/upload/?folder_id=${encodeURIComponent(payload.folderId)}`,
      payload.flows,
    );
    return res.data;
  };

  const mutation = mutate(["usePostUploadFlowToFolder"], uploadFlowToFolderFn, {
    ...options,
    onSettled: (res) => {
      queryClient.refetchQueries({
        queryKey: ["useGetFolders"],
      });
      queryClient.refetchQueries({
        queryKey: ["useGetFolder"],
      });
    },
  });

  return mutation;
};
