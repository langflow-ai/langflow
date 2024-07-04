import { useMutationFunctionType } from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostUploadFile {
  file: File;
  id: string;
}

export const usePostUploadFile: useMutationFunctionType<IPostUploadFile> = ({
  callbackSuccess,
  callbackError,
}) => {
  const { mutate } = UseRequestProcessor();

  const postUploadFileFn = async (payload: IPostUploadFile): Promise<any> => {
    const formData = new FormData();
    formData.append("file", payload.file);

    const response = await api.post<any>(
      `${getURL("FILES")}/upload/${payload.id}`,
      formData,
    );

    return { data: response.data, file: payload.file };
  };

  const mutation: UseMutationResult<any, any, IPostUploadFile> = mutate(
    ["usePostUploadFile"],
    async (payload: IPostUploadFile) => {
      const res = await postUploadFileFn(payload);
      return res;
    },
    {
      onError: (err) => {
        if (callbackError) {
          callbackError(err);
        }
      },
      onSuccess: (data) => {
        if (callbackSuccess) {
          callbackSuccess(data.data, data.file);
        }
      },
    },
  );

  return mutation;
};
