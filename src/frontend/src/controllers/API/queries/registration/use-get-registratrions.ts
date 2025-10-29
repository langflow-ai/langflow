import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface RegistrationInfo {
  email: string;
  registered_at: string;
  langflow_connected: boolean;
}

export interface IRegistrationResponse {
  total: number;
  registrations: RegistrationInfo[];
}

export const useGetRegistrations: useQueryFunctionType<
  undefined,
  IRegistrationResponse
> = (options?) => {
  const { query } = UseRequestProcessor();

  const getRegistrations = async (): Promise<IRegistrationResponse> => {
    const res = await api.get(`${getURL("REGISTRATION", {}, true)}/`);
    return res.data;
  };

  const queryResult: UseQueryResult<IRegistrationResponse, any> = query(
    ["useGetRegistrations"],
    getRegistrations,
    {
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
