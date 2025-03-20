import { useMessagesStore } from "@/stores/messagesStore";
import { UseMutationResult } from "@tanstack/react-query";
import { ColDef, ColGroupDef } from "ag-grid-community";
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

export const useGetMessagesMutation = (
  options?: any,
): UseMutationResult<
  MessagesResponse,
  unknown,
  MessagesQueryParams,
  unknown
> => {
  const { mutate } = UseRequestProcessor();

  const getMessagesFn = async (
    payload: MessagesQueryParams,
  ): Promise<MessagesResponse> => {
    const { id, mode, excludedFields, params } = payload;
    const config = {};
    if (id) {
      config["params"] = { flow_id: id };
    }
    if (params) {
      config["params"] = { ...config["params"], ...params };
    }

    const data = await api.get<any>(`${getURL("MESSAGES")}`, config);
    const columns = extractColumnsFromRows(data.data, mode, excludedFields);
    useMessagesStore.getState().setMessages(data.data);

    return { rows: data.data, columns };
  };

  // Cast the mutation to the correct type
  const mutation = mutate(
    ["useGetMessagesMutation"],
    getMessagesFn,
    options,
  ) as UseMutationResult<
    MessagesResponse,
    unknown,
    MessagesQueryParams,
    unknown
  >;

  return mutation;
};
