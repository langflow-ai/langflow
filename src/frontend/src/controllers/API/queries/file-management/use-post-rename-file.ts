import { useMutationFunctionType } from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostRenameFile {
  id: string;
  name: string;
}

export const usePostRenameFileV2: useMutationFunctionType<
  undefined,
  IPostRenameFile
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const postRenameFileFn = async (payload: IPostRenameFile): Promise<any> => {
    const response = await api.put<any>(
      `${getURL("FILE_MANAGEMENT")}/${payload.id}`,
      { name: payload.name },
    );

    return response.data;
  };

  const mutation: UseMutationResult<IPostRenameFile, any, IPostRenameFile> =
    mutate(
      ["usePostRenameFileV2"],
      async (payload: IPostRenameFile) => {
        const res = await postRenameFileFn(payload);
        return res;
      },
      options,
    );

  return mutation;
};
