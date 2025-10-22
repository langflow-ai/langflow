import type { UseMutationResult } from "@tanstack/react-query";
import type {
  APICodeValidateType,
  ResponseErrorDetailAPI,
  useMutationFunctionType,
} from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostValidateCode {
  code: string;
}

export const usePostValidateCode: useMutationFunctionType<
  undefined,
  IPostValidateCode,
  APICodeValidateType,
  ResponseErrorDetailAPI
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const postValidateCodeFn = async (
    payload: IPostValidateCode,
  ): Promise<APICodeValidateType> => {
    const response = await api.post<APICodeValidateType>(
      getURL("VALIDATE", { 1: "code" }),
      {
        code: payload.code,
      },
    );

    return response.data;
  };

  const mutation: UseMutationResult<
    APICodeValidateType,
    ResponseErrorDetailAPI,
    IPostValidateCode
  > = mutate(["usePostValidateCode"], postValidateCodeFn, options);

  return mutation;
};
