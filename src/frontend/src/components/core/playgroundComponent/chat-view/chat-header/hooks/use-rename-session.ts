import { useCallback, useState } from "react";

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

  const handleEditSave = useCallback(
    async (newSessionId: string) => {
      if (
        !currentSessionId ||
        !newSessionId.trim() ||
        newSessionId.trim() === currentSessionId
      ) {
        setIsEditing(false);
        return;
      }
      await handleRename(currentSessionId, newSessionId.trim());
      onSessionSelect?.(newSessionId.trim());
      setIsEditing(false);
    },
    [currentSessionId, handleRename, onSessionSelect],
  );

  const handleEditStart = useCallback(() => {
    setIsEditing(true);
  }, []);

  return {
    isEditing,
    handleEditSave,
    handleEditStart,
  };
};
