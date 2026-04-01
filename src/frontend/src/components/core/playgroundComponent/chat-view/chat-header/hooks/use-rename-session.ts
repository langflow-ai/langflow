import { useCallback, useEffect, useState } from "react";

interface UseRenameSessionParams {
  currentSessionId?: string;
  handleRename: (sessionId: string, newSessionId: string) => Promise<void>;
  onSessionSelect?: (sessionId: string) => void;
}

export const useRenameSession = ({
  currentSessionId,
  handleRename,
  onSessionSelect,
}: UseRenameSessionParams) => {
  const [isEditing, setIsEditing] = useState(false);

  // Reset edit state when the active session changes.
  useEffect(() => {
    setIsEditing(false);
  }, [currentSessionId]);

  const handleEditStart = useCallback(() => {
    setIsEditing(true);
  }, []);

  const handleEditCancel = useCallback(() => {
    setIsEditing(false);
  }, []);

  const handleEditSave = useCallback(
    async (newSessionId: string) => {
      const trimmed = newSessionId.trim();
      if (!currentSessionId || !trimmed || trimmed === currentSessionId) {
        setIsEditing(false);
        return;
      }
      onSessionSelect?.(trimmed);
      await handleRename(currentSessionId, trimmed);
      setIsEditing(false);
    },
    [currentSessionId, handleRename, onSessionSelect],
  );

  return { isEditing, handleEditStart, handleEditCancel, handleEditSave };
};
