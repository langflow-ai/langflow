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
  mode: "union" | "intersection";
  excludedColumns?: string[];
}

interface PaginationType {
  page?: number;
  size?: number;
  total?: number;
  pages?: number;
}

interface TransactionsPagination extends PaginationType {
  items?: Array<object>;
}

interface TransactionsResponse {
  pagination: PaginationType;
  rows: Array<object>;
  columns: Array<ColDef | ColGroupDef>;
}

export const useGetTransactionsQuery: useQueryFunctionType<
  TransactionsQueryParams,
  TransactionsResponse
> = ({ id, excludedColumns, mode, params }, options) => {
  // Function body remains unchanged
  const { query } = UseRequestProcessor();

  const responseFn = (data: TransactionsPagination) => {
    const pagination: PaginationType = { ...data };

    const rows = data.items ?? [];
    const columns = extractColumnsFromRows(rows, mode, excludedColumns);
    return { pagination: pagination, rows: rows, columns };
  };

  const getTransactionsFn = async () => {
    const config = {};
    config["params"] = { flow_id: id };
    if (params) {
      config["params"] = { ...config["params"], ...params };
    }

    const result = await api.get<TransactionsPagination>(
      `${getURL("TRANSACTIONS")}`,
      config,
    );

    return responseFn(result.data);
  };

  const queryResult = query(
    ["useGetTransactionsQuery", id, { ...params }],
    getTransactionsFn,
    {
      placeholderData: keepPreviousData,
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
