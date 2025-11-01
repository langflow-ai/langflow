import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface RegistrationInfo {
  email: string;
  registered_at: string;
}

export const useGetRegistration: useQueryFunctionType<
  undefined,
  RegistrationInfo
> = (options?) => {
  const { query } = UseRequestProcessor();

  const getRegistration = async (): Promise<RegistrationInfo> => {
    const res = await api.get(`${getURL("REGISTRATION", {}, true)}/`);
    return res.data;
  };

  const queryResult: UseQueryResult<RegistrationInfo, any> = query(
    ["useGetRegistration"],
    getRegistration,
    {
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
