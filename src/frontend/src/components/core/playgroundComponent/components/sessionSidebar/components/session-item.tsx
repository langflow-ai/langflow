import { DEFAULT_SESSION_NAME } from "@/constants/constants";
import useFlowStore from "@/stores/flowStore";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import { cn } from "@/utils/utils";
import { useRenameSession } from "../../../hooks/use-rename-session";
import { SessionMenuDropdown } from "../../sessionMenuDropdown/session-menu-dropdown";
import { MenuEllipsisButton } from "./menu-ellipsis-button";

export const SessionItem = ({
  sessionId,
  onRename,
  onDelete,
  onLogs,
}: {
  sessionId: string;
  onRename: (sessionId: string, newSessionId: string) => void;
  onDelete: (sessionId: string) => void;
  onLogs: () => void;
}) => {
  const flowId = useFlowStore((state) => state.currentFlow?.id);
  const selectedSession = usePlaygroundStore((state) => state.selectedSession);
  const setSelectedSession = usePlaygroundStore(
    (state) => state.setSelectedSession
  );

  const { isEditing, handleEditSave, handleEditStart } = useRenameSession({
    handleRename: onRename,
  });

  const handleClick = () => {
    setSelectedSession(sessionId);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter") {
      handleClick();
    }
  };

  const handleDelete = () => {
    onDelete(sessionId);
  };
  const canEdit = sessionId !== flowId;

  return (
    // biome-ignore lint/a11y/useSemanticElements: Can't use button because it will conflict with internal button
    <div
      className={cn(
        "flex items-center justify-between transition-colors duration-75 gap-2 w-full px-2 h-8 hover:bg-muted rounded-md",
        selectedSession === sessionId && "bg-muted"
      )}
      role="button"
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      tabIndex={0}
    >
      <span className="text-mmd font-medium">
        {canEdit ? sessionId : DEFAULT_SESSION_NAME}
      </span>
      <SessionMenuDropdown
        onLogs={onLogs}
        onRename={handleEditStart}
        onDelete={handleDelete}
      >
        <MenuEllipsisButton />
      </SessionMenuDropdown>
    </div>
  );
};
