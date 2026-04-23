import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IClientIpResponse {
  ip: string | null;
}

export const useGetClientIpQuery: useQueryFunctionType<
  undefined,
  IClientIpResponse
> = (options) => {
  const { query } = UseRequestProcessor();

  const getClientIpFn = async () => {
    return await api.get<IClientIpResponse>(`${getURL("API_KEY")}/client-ip`);
  };

  const responseFn = async () => {
    const { data } = await getClientIpFn();
    return data;
  };

  const queryResult = query(["useGetClientIpQuery"], responseFn, {
    ...options,
  });

  return queryResult;
};
