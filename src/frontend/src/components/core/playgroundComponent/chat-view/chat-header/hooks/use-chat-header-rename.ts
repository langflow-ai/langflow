import { useCallback, useState } from "react";
import { useUpdateSessionName } from "@/controllers/API/queries/messages/use-rename-session";
import { isNoMessagesError } from "../utils/is-no-messages-error";

interface UseChatHeaderRenameProps {
  currentSessionId?: string;
  onSessionSelect?: (sessionId: string) => void;
}

export function useChatHeaderRename({
  currentSessionId,
  onSessionSelect,
}: UseChatHeaderRenameProps) {
  const [isEditing, setIsEditing] = useState(false);
  const { mutate: updateSessionName } = useUpdateSessionName();

  const handleRename = useCallback(() => {
    if (!currentSessionId) {
      return;
    }
    setIsEditing(true);
  }, [currentSessionId]);

  const handleRenameSave = useCallback(
    (newSessionId: string) => {
      if (
        !currentSessionId ||
        !newSessionId.trim() ||
        newSessionId.trim() === currentSessionId
      ) {
        setIsEditing(false);
        return;
      }

      const trimmedNewId = newSessionId.trim();

      // Optimistically update the UI immediately
      setIsEditing(false);
      if (onSessionSelect) {
        onSessionSelect(trimmedNewId);
      }

      // Then update via API in the background
      updateSessionName(
        {
          old_session_id: currentSessionId,
          new_session_id: trimmedNewId,
        },
        {
          onSuccess: () => {
            // Already updated optimistically, just ensure state is correct
            if (onSessionSelect) {
              onSessionSelect(trimmedNewId);
            }
          },
          onError: (error: unknown) => {
            // If it's a "no messages found" error, the session exists in sessionStorage
            // but not in the database. The optimistic update already handled this.
            if (!isNoMessagesError(error) && onSessionSelect) {
              // For other errors, revert to the old session ID
              onSessionSelect(currentSessionId);
            }
          },
        },
      );
    },
    [currentSessionId, updateSessionName, onSessionSelect],
  );

  return {
    isEditing,
    handleRename,
    handleRenameSave,
  };
}
