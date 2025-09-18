import { keepPreviousData } from "@tanstack/react-query";
import type { Message } from "@/types/messages";
import type { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface SessionsQueryParams {
  flowId?: string;
  useLocalStorage?: boolean;
}

type SessionsResponse = string[];

export const useGetSessionsFromFlowQuery: useQueryFunctionType<
  SessionsQueryParams,
  SessionsResponse
> = ({ flowId, useLocalStorage }, options) => {
  const { query } = UseRequestProcessor();

  const getSessionsFn = async () => {
    if (!flowId) {
      return [];
    }

    let sessionIds: string[] = [];

    if (!useLocalStorage) {
      const response = await api.get<string[]>(
        `${getURL("MESSAGES")}/sessions`,
        {
          params: { flow_id: flowId },
        },
      );
      sessionIds = response.data ?? [];
    } else {
      // For playground mode, get sessions from sessionStorage
      const data = JSON.parse(
        window.sessionStorage.getItem(flowId ?? "") || "[]",
      );
      // Extract unique session IDs from stored messages
      const sessionIdsSet = new Set(
        data.map((msg: Message) => msg.session_id).filter(Boolean),
      );

      sessionIds = Array.from(sessionIdsSet) as string[];
    }

    sessionIds = sessionIds.filter((id) => id !== flowId);
    if (flowId) {
      sessionIds.unshift(flowId);
    }

    return sessionIds;
  };

  const queryResult = query(
    ["useGetSessionsFromFlowQuery", { flowId }],
    getSessionsFn,
    {
      placeholderData: keepPreviousData,
      ...options,
    },
  );

  return queryResult;
};
