import { useMessagesStore } from "@/stores/messagesStore";
import { keepPreviousData } from "@tanstack/react-query";
import { ColDef, ColGroupDef } from "ag-grid-community";
import { useQueryFunctionType } from "../../../../types/api";
import { extractColumnsFromRows } from "../../../../utils/utils";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface MessagesQueryParams {
  id?: string;
  mode: "intersection" | "union";
  excludedFields?: string[];
  params?: object;
}

interface MessagesResponse {
  rows: Array<object>;
  columns: Array<ColDef | ColGroupDef>;
}

export const useGetMessagesQuery: useQueryFunctionType<
  MessagesQueryParams,
  MessagesResponse
> = ({ id, mode, excludedFields, params }, options) => {
  const { query } = UseRequestProcessor();

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

  const responseFn = async () => {
    const data = await getMessagesFn(id, params);
    const columns = extractColumnsFromRows(data.data, mode, excludedFields);
    useMessagesStore.getState().setMessages(data.data);
    return { rows: data, columns };
  };

  const queryResult = query(["useGetMessagesQuery", { id }], responseFn, {
    placeholderData: keepPreviousData,
    ...options,
  });

  return queryResult;
};
