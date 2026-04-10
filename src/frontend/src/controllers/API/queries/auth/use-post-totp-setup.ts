import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface TOTPSetupResponse {
  provisioning_uri: string;
  raw_secret: string;
}

export const usePostTotpSetup: useMutationFunctionType<undefined, void> = (
  options?,
) => {
  const { mutate } = UseRequestProcessor();

  async function setupTotp(): Promise<TOTPSetupResponse> {
    const res = await api.post<TOTPSetupResponse>(`${getURL("TOTP_SETUP")}`);
    return res.data;
  }

  const mutation: UseMutationResult<TOTPSetupResponse, Error, void> = mutate(
    ["usePostTotpSetup"],
    setupTotp,
    { retry: false, ...options },
  );

  return mutation;
};
