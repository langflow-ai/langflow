import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IRegistrationRequest {
  email: string;
}

interface IRegistrationResponse {
  email: string;
}

export const usePostRegistration: useMutationFunctionType<
  undefined,
  IRegistrationRequest
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const postRegistrationFn = async (
    payload: IRegistrationRequest,
  ): Promise<IRegistrationResponse> => {
    const response = await api.post(`${getURL("REGISTRATION", {}, true)}/`, {
      email: payload.email,
    });
    return response.data;
  };

  const mutation: UseMutationResult<
    IRegistrationResponse,
    Error | unknown,
    IRegistrationRequest
  > = mutate(["usePostRegistration"], postRegistrationFn, {
    ...options,
    onSettled: (response) => {
      if (response?.success) {
        queryClient.refetchQueries({
          queryKey: ["useGetRegistration"],
        });
      }
    },
  });

  return mutation;
};
