import { useState } from "react";

export const useRenameSession = ({
  handleRename,
}: {
  handleRename: (sessionId: string, newSessionId: string) => Promise<void>;
}) => {
  const [isEditing, setIsEditing] = useState(false);

  const handleEditSave = async (sessionId: string, newSessionId: string) => {
    if (!newSessionId.trim() || !sessionId || newSessionId === sessionId) {
      setIsEditing(false);
      return;
    }
    await handleRename(sessionId, newSessionId);
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
