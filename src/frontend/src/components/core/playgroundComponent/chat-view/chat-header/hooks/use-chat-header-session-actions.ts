import { useCallback, useState } from "react";

interface UseChatHeaderSessionActionsProps {
  currentSessionId?: string;
  onDeleteSession?: (sessionId: string) => void;
}

export function useChatHeaderSessionActions({
  currentSessionId,
  onDeleteSession,
}: UseChatHeaderSessionActionsProps) {
  const [openLogsModal, setOpenLogsModal] = useState(false);

  const handleMessageLogs = useCallback(() => {
    if (currentSessionId) {
      // Use setTimeout to ensure the Select has closed before opening the modal
      setTimeout(() => {
        setOpenLogsModal(true);
      }, 150);
    }
  }, [currentSessionId]);

  const handleDelete = useCallback(() => {
    if (currentSessionId && onDeleteSession) {
      onDeleteSession(currentSessionId);
    }
  }, [currentSessionId, onDeleteSession]);

  return {
    openLogsModal,
    setOpenLogsModal,
    handleMessageLogs,
    handleDelete,
  };
}
