import { useCallback, useMemo } from "react";
import type { SessionMoreMenuProps } from "../components/session-more-menu";

type Handlers = Pick<SessionMoreMenuProps, "onMessageLogs">;

type UseSessionMoreMenuHandlersParams = {
  currentSessionId?: string | null;
  onOpenLogs?: (triggerElement: HTMLElement | null) => void;
};

// Centralizes the menu actions for the header: rename, message logs, delete.
export function useSessionMoreMenuHandlers({
  currentSessionId,
  onOpenLogs,
}: UseSessionMoreMenuHandlersParams): Handlers {
  const handleMessageLogs = useCallback(
    (triggerElement: HTMLElement | null) => {
      if (!onOpenLogs || !currentSessionId) return;
      onOpenLogs(triggerElement);
    },
    [currentSessionId, onOpenLogs],
  );

  return useMemo(
    () => ({
      onMessageLogs: onOpenLogs ? handleMessageLogs : undefined,
    }),
    [handleMessageLogs, onOpenLogs],
  );
}
