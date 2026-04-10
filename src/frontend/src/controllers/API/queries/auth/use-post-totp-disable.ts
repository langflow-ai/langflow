import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface TOTPDisableParams {
  code: string;
}

interface TOTPStatusResponse {
  totp_enabled: boolean;
}

export const usePostTotpDisable: useMutationFunctionType<
  undefined,
  TOTPDisableParams
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  async function disableTotp(
    params: TOTPDisableParams,
  ): Promise<TOTPStatusResponse> {
    const res = await api.post<TOTPStatusResponse>(
      `${getURL("TOTP_DISABLE")}`,
      params,
    );
    return res.data;
  }

  const mutation: UseMutationResult<
    TOTPStatusResponse,
    Error,
    TOTPDisableParams
  > = mutate(["usePostTotpDisable"], disableTotp, { retry: false, ...options });

  return mutation;
};
