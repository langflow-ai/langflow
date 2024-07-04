import { keepPreviousData } from "@tanstack/react-query";
import { ColDef, ColGroupDef } from "ag-grid-community";
import { useQueryFunctionType } from "../../../../types/api";
import { extractColumnsFromRows } from "../../../../utils/utils";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface TransactionsQueryParams {
  id: string;
  params?: Record<string, unknown>;
}

interface TransactionsResponse {
  rows: Array<object>;
  columns: Array<ColDef | ColGroupDef>;
}

export const useGetHealthQuery: useQueryFunctionType<
  undefined,
  TransactionsResponse
> = (_, onFetch) => {
  const { query } = UseRequestProcessor();

  const responseFn = (data: any) => {
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
   * @returns {Promise<AxiosResponse<any>>} A promise that resolves to an AxiosResponse containing the health status.
   */
  async function getHealthFn() {
    return await api.get("/health_check");
    // Health is the only endpoint that doesn't require /api/v1
  }

  const queryResult = query(
    ["useGetHealthQuery"],
    async () => {
      const result = await getHealthFn();
      return responseFn(result);
    },
    {
      placeholderData: keepPreviousData,
      refetchInterval: 20000,
    },
  );

  return queryResult;
};
