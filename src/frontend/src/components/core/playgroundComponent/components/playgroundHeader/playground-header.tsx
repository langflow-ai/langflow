import { useShallow } from "zustand/react/shallow";
import { DEFAULT_SESSION_NAME } from "@/constants/constants";
import useFlowStore from "@/stores/flowStore";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import { HeaderButton } from "./components/header-button";
import { SessionManagerDropdown } from "./components/session-manager-dropdown";
import { SessionMenuDropdown } from "./components/session-menu-dropdown";
import { SessionRename } from "./components/session-rename";
import { useEditSessionInfo } from "./hooks/use-edit-session-info";

export function PlaygroundHeader() {
  const selectedSession = usePlaygroundStore((state) => state.selectedSession);

  const flowId = useFlowStore(useShallow((state) => state.currentFlow?.id));

  const sessionName =
    selectedSession === flowId ? DEFAULT_SESSION_NAME : selectedSession;

  const { isEditing, handleEditSave, handleEditStart, handleDelete } =
    useEditSessionInfo({
      flowId,
    });

  return (
    <div className="flex items-center justify-between gap-2 px-4 py-3">
      <div className="flex items-center gap-2 flex-1 overflow-hidden">
        <SessionManagerDropdown>
          <HeaderButton icon="ListRestart" />
        </SessionManagerDropdown>
        <div className="truncate text-sm w-full font-medium text-secondary-foreground">
          {isEditing ? (
            <SessionRename
              sessionId={selectedSession}
              onSave={handleEditSave}
            />
          ) : (
            sessionName
          )}
        </div>
      </div>
      <div className="flex items-center gap-1">
        <SessionMenuDropdown
          onRename={handleEditStart}
          onDelete={handleDelete}
          onLogs={() => {}}
        >
          <HeaderButton icon="MoreVertical" />
        </SessionMenuDropdown>

        <HeaderButton icon="Expand" onClick={() => {}} />
      </div>
    </div>
  );
}
