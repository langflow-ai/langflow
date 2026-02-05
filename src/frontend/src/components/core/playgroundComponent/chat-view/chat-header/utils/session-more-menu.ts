import type { SessionMoreMenuProps } from "../components/session-more-menu";

type Handlers = Pick<
  SessionMoreMenuProps,
  "onRename" | "onMessageLogs" | "onDelete"
>;

export function buildChatHeaderSessionMenuHandlers({
  currentSessionId,
  handleEditStart,
  setOpenLogsModal,
  handleDeleteSessionInternal,
}: {
  currentSessionId?: string | null;
  handleEditStart: () => void;
  setOpenLogsModal: (open: boolean) => void;
  handleDeleteSessionInternal: () => void;
}): Handlers {
  return {
    onRename: handleEditStart,
    onMessageLogs: () => {
      if (currentSessionId) {
        setOpenLogsModal(true);
      }
    },
    onDelete: handleDeleteSessionInternal,
  };
}

export function buildSessionSelectorMenuHandlers({
  sessionId,
  onRename,
  inspectSession,
  deleteSession,
}: {
  sessionId: string;
  onRename: () => void;
  inspectSession?: (sessionId: string) => void;
  deleteSession: (sessionId: string) => void;
}): Handlers {
  return {
    onRename,
    onMessageLogs: () => inspectSession?.(sessionId),
    onDelete: () => deleteSession(sessionId),
  };
}
