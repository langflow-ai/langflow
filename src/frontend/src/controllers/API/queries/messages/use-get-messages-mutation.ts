import useFlowStore from "@/stores/flowStore";
import { useMessagesStore } from "@/stores/messagesStore";
import { useMutationFunctionType } from "@/types/api";
import { useQueryClient } from "@tanstack/react-query";
import { ColDef, ColGroupDef } from "ag-grid-community";
import {
  extractColumnsFromRows,
  prepareSessionIdForAPI,
} from "../../../../utils/utils";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface MessagesQueryParams {
  id?: string;
  session_id?: string;
  sender?: string;
  sender_name?: string;
  order_by?: string;
  mode: "intersection" | "union";
  excludedFields?: string[];
  params?: object;
}

interface MessagesResponse {
  rows: Array<object>;
  columns: Array<ColDef | ColGroupDef>;
}

export const useGetMessagesMutation: useMutationFunctionType<
  undefined,
  MessagesQueryParams
> = (options) => {
  const { mutate } = UseRequestProcessor();
  const queryClient = useQueryClient();

  const getMessagesFn = async (
    payload: MessagesQueryParams,
  ): Promise<MessagesResponse> => {
    const {
      id,
      session_id,
      sender,
      sender_name,
      order_by,
      mode,
      excludedFields,
      params,
    } = payload;
    const isPlaygroundPage = useFlowStore.getState().playgroundPage;
    const config = {};

    const buildQueryParams = (params: Partial<MessagesQueryParams>) => {
      const queryParams = {};
      const paramMap = {
        id: "flow_id",
        session_id: "session_id",
        sender: "sender",
        sender_name: "sender_name",
        order_by: "order_by",
      };

      Object.entries(paramMap).forEach(([key, apiKey]) => {
        if (params[key]) {
          // Special handling for session_id to ensure proper URL encoding
          if (key === "session_id") {
            queryParams[apiKey] = prepareSessionIdForAPI(params[key]);
          } else {
            queryParams[apiKey] = params[key];
          }
        }
      });

      return queryParams;
    };

    const queryParams = buildQueryParams({
      id,
      session_id,
      sender,
      sender_name,
      order_by,
    });
    config["params"] = { ...queryParams, ...params };

    let data;
    if (!isPlaygroundPage) {
      const response = await api.get<any>(`${getURL("MESSAGES")}`, config);
      data = response.data;
    } else {
      data = JSON.parse(window.sessionStorage.getItem(id ?? "") || "[]");
    }

    const columns = extractColumnsFromRows(data, mode, excludedFields);
    useMessagesStore.getState().setMessages(data);

    return { rows: data, columns };
  };

  const mutation = mutate(["useGetMessagesMutation"], getMessagesFn, {
    ...options,
    onSettled: (response) => {
      if (response) {
        queryClient.refetchQueries({
          queryKey: ["useGetMessagesQuery"],
        });
      }
    },
  });

  return mutation;
};
