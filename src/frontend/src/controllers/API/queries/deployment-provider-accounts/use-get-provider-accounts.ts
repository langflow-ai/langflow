import type { ProviderAccount } from "@/pages/MainPage/pages/deploymentsPage/types";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface ProviderAccountListResponse {
  providers: ProviderAccount[];
  page: number;
  size: number;
  total: number;
}

interface GetProviderAccountsParams {
  page?: number;
  size?: number;
}

export const useGetProviderAccounts: useQueryFunctionType<
  GetProviderAccountsParams,
  ProviderAccountListResponse
> = ({ page = 1, size = 20 } = {}, options) => {
  const { query } = UseRequestProcessor();

  const getProviderAccountsFn =
    async (): Promise<ProviderAccountListResponse> => {
      const { data } = await api.get<ProviderAccountListResponse>(
        `${getURL("DEPLOYMENT_PROVIDER_ACCOUNTS")}`,
        { params: { page, size } },
      );
      return data;
    };

  return query(
    ["useGetProviderAccounts", { page, size }],
    getProviderAccountsFn,
    options,
  );
};
