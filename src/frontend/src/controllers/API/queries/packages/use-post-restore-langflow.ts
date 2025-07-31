import { useMutation } from "@tanstack/react-query";
import { AxiosError } from "axios";
import { BASE_URL_API } from "@/constants/constants";
import { api } from "../../api";

export interface RestoreLangflowRequest {
  confirm: boolean;
}

export interface RestoreLangflowResponse {
  message: string;
  status: string;
}

async function restoreLangflowRequest(
  confirm: boolean = true,
): Promise<RestoreLangflowResponse> {
  const response = await api.post(`${BASE_URL_API}packages/restore`, {
    confirm: confirm,
  });
  return response.data;
}

export const useRestoreLangflow = () => {
  return useMutation<RestoreLangflowResponse, AxiosError, boolean>({
    mutationFn: restoreLangflowRequest,
  });
};
