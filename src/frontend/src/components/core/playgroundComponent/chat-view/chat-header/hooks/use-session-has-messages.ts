import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { Message } from "@/types/messages";

interface UseSessionHasMessagesParams {
  sessionId?: string | null;
  flowId?: string;
}

/**
 * Hook to check if a session has any messages.
 * Returns true if the session has at least one message, false otherwise.
 */
export const useSessionHasMessages = ({
  sessionId,
  flowId,
}: UseSessionHasMessagesParams): boolean => {
  const queryClient = useQueryClient();

  if (!flowId) {
    return false;
  }

  const sessionCacheKey = [
    "useGetMessagesQuery",
    { id: flowId, session_id: sessionId },
  ];

  const { data: sessionMessages = [] } = useQuery<Message[]>({
    queryKey: sessionCacheKey,
    queryFn: () => {
      const cachedData =
        queryClient.getQueryData<Message[]>(sessionCacheKey) || [];
      return cachedData;
    },
    staleTime: Infinity,
    gcTime: 5 * 60 * 1000,
    structuralSharing: false,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    enabled: !!flowId,
  });

  const hasMessages = sessionMessages.some((message: Message) => {
    const isCurrentFlow = message.flow_id === flowId;

    if (sessionId === flowId) {
      return (
        isCurrentFlow &&
        (message.session_id === sessionId || !message.session_id)
      );
    }

    return isCurrentFlow && message.session_id === sessionId;
  });

  return hasMessages;
};
