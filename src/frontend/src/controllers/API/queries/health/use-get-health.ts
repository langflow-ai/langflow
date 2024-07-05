import { keepPreviousData } from "@tanstack/react-query";
import { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { UseRequestProcessor } from "../../services/request-processor";

interface getHealthResponse {
  status: string;
  chat: string;
  db: string;
  folder: string;
  variables: string;
}

export const useGetHealthQuery: useQueryFunctionType<
  undefined,
  getHealthResponse
> = (_, options) => {
  const { query } = UseRequestProcessor();

  /**
   * Fetches the health status of the API.
   *
   * @returns {Promise<AxiosResponse<TransactionsResponse>>} A promise that resolves to an AxiosResponse containing the health status.
   */
  async function getHealthFn() {
    return (await api.get("/health_check")).data;
    // Health is the only endpoint that doesn't require /api/v1
  }

  const queryResult = query(["useGetHealthQuery"], getHealthFn, {
    placeholderData: keepPreviousData,
    refetchInterval: 20000,
    ...options,
  });

  return queryResult;
};
