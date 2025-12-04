import { useCallback, useState } from "react";
import { useUpdateSessionName } from "@/controllers/API/queries/messages/use-rename-session";
import { useMessagesStore } from "@/stores/messagesStore";
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
  const renameSession = useMessagesStore((state) => state.renameSession);

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
      setIsEditing(false);

      // Update via API first, then update UI on success
      updateSessionName(
        {
          old_session_id: currentSessionId,
          new_session_id: trimmedNewId,
        },
        {
          onSuccess: () => {
            // Update messages in store with new session ID
            renameSession(currentSessionId, trimmedNewId);
            // Then update the selected session
            if (onSessionSelect) {
              onSessionSelect(trimmedNewId);
            }
          },
          onError: (error: unknown) => {
            // If it's a "no messages found" error, the session may be new (no messages yet)
            // In this case, we can still update the local session ID
            if (isNoMessagesError(error) && onSessionSelect) {
              renameSession(currentSessionId, trimmedNewId);
              onSessionSelect(trimmedNewId);
            } else {
              // For other errors, keep the old session ID and log the error
              console.error("Failed to rename session:", error);
            }
          },
        },
      );
    },
    [currentSessionId, updateSessionName, onSessionSelect, renameSession],
  );

  return {
    isEditing,
    handleRename,
    handleRenameSave,
  };
}
