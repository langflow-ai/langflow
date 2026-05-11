import { useCallback, useMemo } from "react";
import type { SessionMoreMenuProps } from "../components/session-more-menu";

type Handlers = Pick<SessionMoreMenuProps, "onMessageLogs">;

type UseSessionMoreMenuHandlersParams = {
  currentSessionId?: string | null;
  onOpenLogs?: () => void;
};

// Centralizes the menu actions for the header: rename, message logs, delete.
export function useSessionMoreMenuHandlers({
  currentSessionId,
  onOpenLogs,
}: UseSessionMoreMenuHandlersParams): Handlers {
  const handleMessageLogs = useCallback(() => {
    if (!onOpenLogs || !currentSessionId) return;
    onOpenLogs();
  }, [currentSessionId, onOpenLogs]);

  return useMemo(
    () => ({
      onMessageLogs: onOpenLogs ? handleMessageLogs : undefined,
    }),
    [handleMessageLogs, onOpenLogs],
  );
}
