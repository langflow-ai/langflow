import { useState } from "react";
import { useDeleteSession } from "@/controllers/API/queries/messages/use-delete-sessions";
import { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";
import { useUpdateSessionName } from "@/controllers/API/queries/messages/use-rename-session";
import { usePlaygroundStore } from "@/stores/playgroundStore";

export const useEditSessionInfo = ({ flowId }: { flowId?: string }) => {
  const [isEditing, setIsEditing] = useState(false);

  const selectedSession = usePlaygroundStore((state) => state.selectedSession);

  const setSelectedSession = usePlaygroundStore(
    (state) => state.setSelectedSession
  );
  const isPlayground = usePlaygroundStore((state) => state.isPlayground);

  const { data: dbSessions } = useGetSessionsFromFlowQuery({
    flowId,
    useLocalStorage: isPlayground,
  });

  const { mutate: updateSessionName } = useUpdateSessionName({
    flowId,
    useLocalStorage: isPlayground,
  });

  const { mutate: deleteSession } = useDeleteSession({
    flowId,
    useLocalStorage: isPlayground,
  });

  const canEdit = selectedSession && selectedSession !== flowId;

  const handleDelete = canEdit
    ? () => {
        if (selectedSession && dbSessions?.includes(selectedSession)) {
          deleteSession({ sessionId: selectedSession });
        }
        setSelectedSession(flowId);
      }
    : undefined;

  const handleEditSave = canEdit
    ? (newSessionId: string) => {
        if (
          !newSessionId.trim() ||
          !selectedSession ||
          newSessionId === selectedSession
        ) {
          setIsEditing(false);
          return;
        }
        if (dbSessions?.includes(selectedSession)) {
          updateSessionName({
            oldSessionId: selectedSession,
            newSessionId,
          });
        }
        setSelectedSession(newSessionId);
        setIsEditing(false);
      }
    : undefined;

  const handleEditStart = canEdit
    ? () => {
        setTimeout(() => {
          setIsEditing(true);
        }, 10);
      }
    : undefined;

  return {
    isEditing,
    handleEditSave,
    handleEditStart,
    handleDelete,
  };
};
