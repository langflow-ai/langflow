import { useMemo } from "react";
import useAuthStore from "@/stores/authStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

const PAGE_SIZE = 100;

interface SessionsPage {
  sessions: string[];
  nextOffset?: number;
}

export function useGetSessionsFromFlowQuery(
  { id }: { id?: string },
  options: { enabled?: boolean } = {},
) {
  const { infiniteQuery } = UseRequestProcessor();
  const playground = useFlowStore((state) => state.playgroundPage);
  const sourceFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const userId = useAuthStore((state) => state.userData?.id);
  const authenticated = useAuthStore((state) => state.isAuthenticated);
  const autoLogin = useAuthStore((state) => state.autoLogin);
  const shared = playground && authenticated && autoLogin === false && !!userId;

  const query = infiniteQuery<SessionsPage>({
    queryKey: [
      "useGetSessionsFromFlowQuery",
      {
        id,
        playground,
        shared,
        userId,
        sourceFlowId: shared ? sourceFlowId : undefined,
      },
      "pages",
    ],
    initialPageParam: 0,
    queryFn: async ({ pageParam }) => {
      let sessionIds: string[];
      if (playground && !shared) {
        const messages: { session_id?: string }[] = JSON.parse(
          window.sessionStorage.getItem(id ?? "") || "[]",
        );
        // Local history is stored in display order. The last occurrence of a
        // session is its most recent message; leave the stored history intact.
        sessionIds = [
          ...new Set(
            messages
              .reverse()
              .map((message) => message.session_id)
              .filter((session): session is string => !!session),
          ),
        ].slice(pageParam, pageParam + PAGE_SIZE + 1);
      } else {
        const response = await api.get<string[]>(
          `${getURL("MESSAGES")}/${shared ? "shared/sessions" : "sessions"}`,
          {
            params: {
              ...(shared
                ? { source_flow_id: sourceFlowId }
                : id
                  ? { flow_id: id }
                  : {}),
              limit: PAGE_SIZE + 1,
              offset: pageParam,
            },
          },
        );
        sessionIds = response.data;
      }
      return {
        sessions: sessionIds.slice(0, PAGE_SIZE),
        // Count server rows before pinning the default session or deduplicating
        // pages. Neither operation may move the next database offset.
        nextOffset:
          sessionIds.length > PAGE_SIZE ? pageParam + PAGE_SIZE : undefined,
      };
    },
    getNextPageParam: (page) => page.nextOffset,
    enabled: options.enabled,
    refetchOnWindowFocus: false,
  });

  const data = useMemo(() => {
    if (!query.data) return undefined;
    const sessions = new Set(query.data.pages.flatMap((page) => page.sessions));
    if (id) sessions.delete(id);
    return { sessions: [...(id ? [id] : []), ...sessions] };
  }, [query.data, id]);

  return { ...query, data };
}
