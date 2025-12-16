import { useState } from "react";

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

  const handleEditSave = async (newSessionId: string) => {
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
  };

  const handleEditStart = () => {
    setTimeout(() => {
      setIsEditing(true);
    }, 10);
  };

  return {
    isEditing,
    handleEditSave,
    handleEditStart,
  };
};
