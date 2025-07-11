import type {
  APIClassType,
  PromptTypeAPI,
  ResponseErrorDetailAPI,
  useMutationFunctionType,
} from "@/types/api";
import type { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostValidatePrompt {
  name: string;
  template: string;
  frontend_node: APIClassType;
}

export const usePostValidatePrompt: useMutationFunctionType<
  undefined,
  IPostValidatePrompt,
  PromptTypeAPI,
  ResponseErrorDetailAPI
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const postValidatePromptFn = async (
    payload: IPostValidatePrompt,
  ): Promise<PromptTypeAPI> => {
    const response = await api.post<PromptTypeAPI>(
      getURL("VALIDATE", { 1: "prompt" }),
      {
        name: payload.name,
        template: payload.template,
        frontend_node: payload.frontend_node,
      },
    );

    return response.data;
  };

  const mutation: UseMutationResult<
    PromptTypeAPI,
    ResponseErrorDetailAPI,
    IPostValidatePrompt
  > = mutate(["usePostValidatePrompt"], postValidatePromptFn, options);

  return mutation;
};
