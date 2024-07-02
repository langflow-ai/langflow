import { ColDef, ColGroupDef } from "ag-grid-community";
import { extractColumnsFromRows } from "../../../../utils/utils";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface TransactionsQueryParams {
  id: string;
  mode: "intersection" | "union";
  params?: Record<string, unknown>;
}

interface TransactionsResponse {
  rows: Array<object>;
  columns: Array<ColDef | ColGroupDef>;
}

export const useGetTransactionsQuery = ({
  id,
  mode,
  params = {},
}: TransactionsQueryParams) => {
  const { query } = UseRequestProcessor();

  const responseFn = async (data) => {
    const columns = extractColumnsFromRows(data.data, mode);
    return { rows: data.data, columns };
  };

  const getTransactionsFn = async (id, mode, params = {}) => {
    const config = {};
    config["params"] = { flow_id: id };
    if (params) {
      config["params"] = { ...config["params"], ...params };
    }

    return await api.get<TransactionsResponse>(
      `${getURL("TRANSACTIONS")}`,
      config,
    );
  };

  const { data, isLoading, isError, refetch } = query(
    ["useGetTransactionsQuery"],
    async () => {
      const rows = await getTransactionsFn(id, mode, params);
      return await responseFn(rows);
    },
    {
      keepPreviousData: true,
    },
  );

  return {
    data,
    isLoading,
    isError,
    refetch,
  };
};

export default useGetTransactionsQuery;
