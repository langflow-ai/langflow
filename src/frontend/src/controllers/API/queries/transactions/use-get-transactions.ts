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
  fetchType: string;
}

interface TransactionsResponse {
  rows: Array<object>;
  columns: Array<ColDef | ColGroupDef>;
}

export const useGetTransactionsQuery: useQueryFunctionType<
  TransactionsQueryParams,
  TransactionsResponse
> = (params, options) => {
  // Function body remains unchanged
  const { query } = UseRequestProcessor();

  const responseFn = (data: object[], fetchType: string) => {
    switch (fetchType) {
      case "TableUnion": {
        const columns = extractColumnsFromRows(data, "union");
        return { rows: data, columns };
      }
      case "TableIntersection": {
        const columns = extractColumnsFromRows(data, "intersection");
        return { rows: data, columns };
      }
      default:
        return data;
    }
  };

  const getTransactionsFn = async () => {
    if (!params) return;
    const config = {};
    config["params"] = { flow_id: params.id };
    if (params.params) {
      config["params"] = { ...config["params"], ...params.params };
    }

    const result = await api.get<object[]>(`${getURL("TRANSACTIONS")}`, config);

    return responseFn(result.data, params.fetchType);
  };

  const queryResult = query(["useGetTransactionsQuery"], getTransactionsFn, {
    placeholderData: keepPreviousData,
    ...options,
  });

  return queryResult;
};
