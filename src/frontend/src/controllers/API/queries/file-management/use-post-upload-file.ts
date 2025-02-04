import { useMutationFunctionType } from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostUploadFile {
  file: File;
}

export const usePostUploadFileV2: useMutationFunctionType<
  undefined,
  IPostUploadFile
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const postUploadFileFn = async (payload: IPostUploadFile): Promise<any> => {
    const formData = new FormData();
    formData.append("file", payload.file);

    const response = await api.post<any>(
      `${getURL("FILE_MANAGEMENT")}/`,
      formData,
    );

    return response.data;
  };

  const mutation: UseMutationResult<IPostUploadFile, any, IPostUploadFile> =
    mutate(
      ["usePostUploadFileV2"],
      async (payload: IPostUploadFile) => {
        const res = await postUploadFileFn(payload);
        return res;
      },
      options,
    );

  return mutation;
};
