import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface TOTPStatusResponse {
  totp_enabled: boolean;
}

export const useGetTotpStatus: useQueryFunctionType<
  undefined,
  TOTPStatusResponse
> = (options?) => {
  const { query } = UseRequestProcessor();

  async function getTotpStatus(): Promise<TOTPStatusResponse> {
    const res = await api.get<TOTPStatusResponse>(`${getURL("TOTP_STATUS")}`);
    return res.data;
  }

  const queryResult: UseQueryResult<TOTPStatusResponse> = query(
    ["useGetTotpStatus"],
    getTotpStatus,
    { staleTime: 0, ...options },
  );

  return queryResult;
};
