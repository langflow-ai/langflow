import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface TOTPEnableParams {
  code: string;
  raw_secret: string;
}

interface TOTPStatusResponse {
  totp_enabled: boolean;
}

export const usePostTotpEnable: useMutationFunctionType<
  undefined,
  TOTPEnableParams
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  async function enableTotp(
    params: TOTPEnableParams,
  ): Promise<TOTPStatusResponse> {
    const res = await api.post<TOTPStatusResponse>(
      `${getURL("TOTP_ENABLE")}`,
      params,
    );
    return res.data;
  }

  const mutation: UseMutationResult<
    TOTPStatusResponse,
    Error,
    TOTPEnableParams
  > = mutate(["usePostTotpEnable"], enableTotp, { retry: false, ...options });

  return mutation;
};
