import { keepPreviousData } from "@tanstack/react-query";
import type { ColDef, ColGroupDef } from "ag-grid-community";
import { isAuthenticatedPlayground } from "@/modals/IOModal/helpers/playground-auth";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useMessagesStore } from "@/stores/messagesStore";
import type { Message } from "@/types/messages";
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
  params?: Record<string, unknown>;
}

interface MessagesResponse {
  rows: Array<object>;
  columns: Array<ColDef | ColGroupDef>;
}

const getStoredMessages = (
  id: string | undefined,
  params: Record<string, unknown>,
): Message[] => {
  const storedMessages = JSON.parse(
    window.sessionStorage.getItem(id ?? "") || "[]",
  ) as Message[];
  const sessionId =
    typeof params.session_id === "string" ? params.session_id : undefined;
  const direction =
    typeof params.order === "string" && params.order.toUpperCase() === "DESC"
      ? -1
      : 1;
  const offset = typeof params.offset === "number" ? params.offset : 0;
  const limit = typeof params.limit === "number" ? params.limit : undefined;

  const filteredMessages = sessionId
    ? storedMessages.filter(
        (message) =>
          message.session_id === sessionId ||
          (sessionId === id && !message.session_id),
      )
    : storedMessages;
  const orderedMessages = [...filteredMessages].sort((a, b) => {
    const timeA = new Date(a.timestamp).getTime();
    const timeB = new Date(b.timestamp).getTime();
    if (Number.isNaN(timeA) || Number.isNaN(timeB)) return 0;
    return direction * (timeA - timeB);
  });

  return orderedMessages.slice(
    offset,
    limit === undefined ? undefined : offset + limit,
  );
};

export const getMessages = async (
  id?: string,
  params: Record<string, unknown> = {},
) => {
  const isPlaygroundPage = useFlowStore.getState().playgroundPage;
  const processedParams = { ...params };
  if (processedParams.session_id) {
    processedParams.session_id = prepareSessionIdForAPI(
      processedParams.session_id as string,
    );
  }

  if (!isPlaygroundPage) {
    return await api.get<Message[]>(`${getURL("MESSAGES")}`, {
      params: {
        ...(id ? { flow_id: id } : {}),
        ...processedParams,
      },
    });
  }

  if (isAuthenticatedPlayground()) {
    const sourceFlowId = useFlowsManagerStore.getState().currentFlowId;
    const sharedParams = { ...processedParams };
    delete sharedParams.flow_id;

    return await api.get<Message[]>(`${getURL("MESSAGES")}/shared`, {
      params: {
        ...sharedParams,
        source_flow_id: sourceFlowId,
      },
    });
  }

  return {
    data: getStoredMessages(id, params),
  };
};

export const useGetMessagesQuery: useQueryFunctionType<
  MessagesQueryParams,
  MessagesResponse
> = ({ id, mode, excludedFields, params }, options) => {
  const { query } = UseRequestProcessor();

  const responseFn = async () => {
    const data = await getMessages(id, params);
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

  const queryResult = query(
    ["useGetMessagesQuery", { id, mode, excludedFields, params }],
    responseFn,
    {
      placeholderData: keepPreviousData,
      ...options,
    },
  );

  return queryResult;
};
