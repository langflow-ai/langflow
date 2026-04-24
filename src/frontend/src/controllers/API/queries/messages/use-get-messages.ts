import { keepPreviousData } from "@tanstack/react-query";
import type { ColDef, ColGroupDef } from "ag-grid-community";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useMessagesStore } from "@/stores/messagesStore";
import { isAuthenticatedPlayground } from "@/modals/IOModal/helpers/playground-auth";
import type { useQueryFunctionType } from "../../../../types/api";
import {
  extractColumnsFromRows,
  prepareSessionIdForAPI,
} from "../../../../utils/utils";
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
    const isPlaygroundPage = useFlowStore.getState().playgroundPage;
    const config = {};
    if (id) {
      config["params"] = { flow_id: id };
    }
    if (params) {
      // Process params to ensure session_id is properly encoded
      const processedParams = { ...params } as any;
      if (processedParams.session_id) {
        processedParams.session_id = prepareSessionIdForAPI(
          processedParams.session_id,
        );
      }
      config["params"] = { ...config["params"], ...processedParams };
    }

    if (!isPlaygroundPage) {
      return await api.get<any>(`${getURL("MESSAGES")}`, config);
    }

    // Authenticated users on playground: fetch ALL messages from DB via shared endpoint
    // (no session_id filter — ChatView filters locally by visibleSession)
    if (isAuthenticatedPlayground()) {
      const sourceFlowId = useFlowsManagerStore.getState().currentFlowId;
      return await api.get<any>(`${getURL("MESSAGES")}/shared`, {
        params: { source_flow_id: sourceFlowId },
      });
    }

    // Anonymous/auto-login: use sessionStorage (original behavior)
    return {
      data: JSON.parse(window.sessionStorage.getItem(id ?? "") || "[]"),
    };
  };

  const responseFn = async () => {
    const data = await getMessagesFn(id, params);
    const columns = extractColumnsFromRows(data.data, mode, excludedFields);

    // For authenticated playground, sync API results into the Zustand store
    // so ChatView (which reads from useMessagesStore) can display them.
    // Replace all messages for this flow to keep store in sync with DB.
    if (isAuthenticatedPlayground() && Array.isArray(data.data)) {
      const store = useMessagesStore.getState();
      const flowId = id;
      // Keep messages from other flows, replace messages for this flow
      const otherFlowMessages = store.messages.filter(
        (m) => m.flow_id !== flowId,
      );
      store.setMessages([...otherFlowMessages, ...data.data]);
    }

    return { rows: data, columns };
  };

  const queryResult = query(["useGetMessagesQuery", { id }], responseFn, {
    placeholderData: keepPreviousData,
    ...options,
  });

  return queryResult;
};
