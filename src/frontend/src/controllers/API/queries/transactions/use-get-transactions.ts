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
  mode?: "union" | "intersection";
  excludedColumns?: string[];
}

interface TransactionsResponse {
  rows: Array<object>;
  columns: Array<ColDef | ColGroupDef>;
}

export const useGetTransactionsQuery: useQueryFunctionType<
  TransactionsQueryParams,
  TransactionsResponse
> = ({ id, excludedColumns, mode, params }, options) => {
  // Function body remains unchanged
  const { query } = UseRequestProcessor();

  const responseFn = (data: object[]) => {
    if (mode) {
      const columns = extractColumnsFromRows(data, mode, excludedColumns);
      return { rows: data, columns };
    } else {
      return data;
    }
  };

  const getTransactionsFn = async () => {
    const config = {};
    config["params"] = { flow_id: id };
    if (params) {
      config["params"] = { ...config["params"], ...params };
    }

    const result = await api.get<object[]>(`${getURL("TRANSACTIONS")}`, config);

    return responseFn(result.data);
  };

  const queryResult = query(["useGetTransactionsQuery"], getTransactionsFn, {
    placeholderData: keepPreviousData,
    refetchOnWindowFocus: false,
    ...options,
  });

  return queryResult;
};
