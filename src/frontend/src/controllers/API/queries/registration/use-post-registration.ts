import type { UseMutationResult } from "@tanstack/react-query";
import { useFolderStore } from "@/stores/foldersStore";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IRegistrationRequest {
  email: string;
}

interface IRegistrationResponse {
  success: boolean;
  message: string;
  email: string;
}

export const usePostRegistration: useMutationFunctionType<
  IRegistrationResponse,
  IRegistrationRequest
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);

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
    any,
    IRegistrationRequest
  > = mutate(["usePostRegistration"], postRegistrationFn, {
    ...options,
    onSettled: (response) => {
      if (response?.success) {
        queryClient.refetchQueries({
          queryKey: ["useGetRegistrations"],
        });
      }
    },
  });

  return mutation;
};
