import { keepPreviousData } from "@tanstack/react-query";
import { ColDef, ColGroupDef } from "ag-grid-community";
import { useQueryFunctionType } from "../../../../types/api";
import { extractColumnsFromRows } from "../../../../utils/utils";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { useMessagesStore } from "@/stores/messagesStore";

interface MessagesQueryParams {
  id?: string;
  mode: "intersection" | "union",
  excludedFields?: string[],
  params?: object;
}

interface MessagesResponse {
  rows: Array<object>;
  columns: Array<ColDef | ColGroupDef>;
};

export const useGetMessagesQuery: useQueryFunctionType<
  MessagesQueryParams,
  MessagesResponse
> = ({ id, mode,excludedFields,params }, onFetch) => {
  const { query } = UseRequestProcessor();

  const responseFn = (
    data: any,
    mode: "intersection" | "union",
    excludedFields?: string[]
) => {
    if (!onFetch) return data;
    if (typeof onFetch === "function") return onFetch(data);
    
    switch (onFetch) {
      case "Table": {
        const columns = extractColumnsFromRows(data.data, mode, excludedFields);
        return { rows: data, columns };
      }
      case "TableSaveState":
        const columns = extractColumnsFromRows(data.data, mode, excludedFields);
        useMessagesStore.getState().setMessages(data.data);
        useMessagesStore.getState().setColumns(columns);
        return { rows: data, columns };
      default:
        return data;
    }
  };

  const getMessagesFn = async (id?: string, params = {}) => {
    const config = {};
    if (id) {
      config["params"] = { flow_id: id };
    }
    if (params) {
      config["params"] = { ...config["params"], ...params };
    }
    return await api.get<any>(`${getURL("MESSAGES")}`, config);
  };

  const queryResult = query(
    ["useGetMessagesQuery"],
    async () => {
      const data = await getMessagesFn(id, params);
      return responseFn(data.data,mode,excludedFields);
    },
    {
    },
  );

  return queryResult;
};
