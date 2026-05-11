import { keepPreviousData } from "@tanstack/react-query";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { isAuthenticatedPlayground } from "@/modals/IOModal/helpers/playground-auth";
import type { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface SessionsQueryParams {
  id?: string;
}

interface SessionsResponse {
  sessions: string[];
}

export const useGetSessionsFromFlowQuery: useQueryFunctionType<
  SessionsQueryParams,
  SessionsResponse
> = ({ id }, options) => {
  const { query } = UseRequestProcessor();

  const getSessionsFn = async (id?: string) => {
    const isPlaygroundPage = useFlowStore.getState().playgroundPage;
    const config = {};
    if (id) {
      config["params"] = { flow_id: id };
    }

    if (!isPlaygroundPage) {
      return await api.get<string[]>(`${getURL("MESSAGES")}/sessions`, config);
    }

    // Authenticated users on playground: fetch sessions from DB
    if (isAuthenticatedPlayground()) {
      const sourceFlowId = useFlowsManagerStore.getState().currentFlowId;
      const response = await api.get<string[]>(
        `${getURL("MESSAGES")}/shared/sessions`,
        { params: { source_flow_id: sourceFlowId } },
      );
      // Ensure the virtual flow_id (default session) is always first
      const sessionIds = response.data ?? [];
      if (id && !sessionIds.includes(id)) {
        sessionIds.unshift(id);
      } else if (id && sessionIds.includes(id)) {
        // Move to front if it exists but isn't first
        const idx = sessionIds.indexOf(id);
        if (idx > 0) {
          sessionIds.splice(idx, 1);
          sessionIds.unshift(id);
        }
      }
      return { data: sessionIds };
    }

    // Anonymous/auto-login: use sessionStorage (original behavior)
    const data = JSON.parse(window.sessionStorage.getItem(id ?? "") || "[]");
    // Extract unique session IDs from stored messages
    const sessionIdsSet = new Set(
      data.map((msg: any) => msg.session_id).filter(Boolean),
    );
    const sessionIds = Array.from(sessionIdsSet);

    // Ensure the flow ID (default session) is always first
    if (id) {
      const idx = sessionIds.indexOf(id);
      if (idx > 0) {
        sessionIds.splice(idx, 1);
        sessionIds.unshift(id);
      } else if (idx === -1) {
        sessionIds.unshift(id);
      }
    }

    return {
      data: sessionIds,
    };
  };

  const responseFn = async () => {
    const response = await getSessionsFn(id);
    return { sessions: response.data };
  };

  const queryResult = query(
    ["useGetSessionsFromFlowQuery", { id }],
    responseFn,
    {
      placeholderData: keepPreviousData,
      ...options,
    },
  );

  return queryResult;
};
