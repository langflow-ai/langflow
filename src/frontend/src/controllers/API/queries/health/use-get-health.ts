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
> = (_, onFetch) => {
  const { query } = UseRequestProcessor();

  const responseFn = (data: getHealthResponse) => {
    if (!onFetch) return data;
    if (typeof onFetch === "function") return onFetch(data);
    switch (onFetch) {
      default:
        return data;
    }
  };

  /**
   * Fetches the health status of the API.
   *
   * @returns {Promise<AxiosResponse<TransactionsResponse>>} A promise that resolves to an AxiosResponse containing the health status.
   */
  async function getHealthFn() {
    return await api.get("/health_check");
    // Health is the only endpoint that doesn't require /api/v1
  }

  const queryResult = query(
    ["useGetHealthQuery"],
    async () => {
      const result = await getHealthFn();
      return responseFn(result.data);
    },
    {
      placeholderData: keepPreviousData,
      refetchInterval: 20000,
    },
  );

  return queryResult;
};
