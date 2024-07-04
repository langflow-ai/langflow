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

export const useGetTransactionsQuery: useQueryFunctionType<
  TransactionsQueryParams,
  TransactionsResponse
> = ({ id, params }, onFetch) => {
  const { query } = UseRequestProcessor();

  const responseFn = (data: any) => {
    if (!onFetch) return data;
    if (typeof onFetch === "function") return onFetch(data);
    switch (onFetch) {
      case "TableUnion": {
        const columns = extractColumnsFromRows(data.data, "union");
        return { rows: data.data, columns };
      }
      case "TableIntersection": {
        const columns = extractColumnsFromRows(data.data, "intersection");
        return { rows: data.data, columns };
      }
      default:
        return data;
    }
  };

  const getTransactionsFn = async () => {
    const config = {};
    config["params"] = { flow_id: id };
    if (params) {
      config["params"] = { ...config["params"], ...params };
    }

    const rows = await api.get<TransactionsResponse>(
      `${getURL("TRANSACTIONS")}`,
      config,
    );

    return responseFn(rows);
  };

  const queryResult = query(["useGetTransactionsQuery"], getTransactionsFn, {
    placeholderData: keepPreviousData,
  });

  return queryResult;
};
