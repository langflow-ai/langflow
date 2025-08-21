import { useState } from "react";
import { useShallow } from "zustand/react/shallow";
import { AnimatedConditional } from "@/components/ui/animated-close";
import { DEFAULT_SESSION_NAME } from "@/constants/constants";
import { useIsMobile } from "@/hooks/use-mobile";
import useFlowStore from "@/stores/flowStore";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import { useEditSessionInfo } from "../../hooks/use-edit-session-info";
import { useRenameSession } from "../../hooks/use-rename-session";
import { SessionLogsModal } from "../../modals/session-logs-modal";
import { SessionManagerDropdown } from "../sessionManagerDropdown/session-manager-dropdown";
import { SessionMenuDropdown } from "../sessionMenuDropdown/session-menu-dropdown";
import { HeaderButton } from "./components/header-button";
import { SessionRename } from "./components/session-rename";

export function PlaygroundHeader() {
  const [openLogsModal, setOpenLogsModal] = useState(false);

  const flowId = useFlowStore(useShallow((state) => state.currentFlow?.id));
  const selectedSession = usePlaygroundStore((state) => state.selectedSession);
  const isFullscreen = usePlaygroundStore((state) => state.isFullscreen);
  const toggleFullscreen = usePlaygroundStore(
    (state) => state.toggleFullscreen
  );
  const isPlayground = usePlaygroundStore((state) => state.isPlayground);
  const setIsOpen = usePlaygroundStore((state) => state.setIsOpen);

  const { handleRename, handleDelete } = useEditSessionInfo({
    flowId,
  });

  const { isEditing, handleEditSave, handleEditStart } = useRenameSession({
    handleRename,
  });

  const isMobile = useIsMobile();

  const onSave = (newSessionId: string) => {
    if (!selectedSession) return;
    handleEditSave(selectedSession, newSessionId);
  };

  const onDelete = () => {
    if (!selectedSession) return;
    handleDelete(selectedSession);
  };

  const onLogs = () => {
    if (!selectedSession) return;
    setOpenLogsModal(true);
  };

  const onClose = () => {
    setIsOpen(false);
  };

  const sessionName =
    selectedSession === flowId ? DEFAULT_SESSION_NAME : selectedSession;

  const isSessionDropdownVisible = !isFullscreen || isMobile;

  return (
    <div className="flex items-center justify-between gap-2 p-4">
      <div className="flex items-center flex-1 overflow-hidden">
        <AnimatedConditional isOpen={isSessionDropdownVisible}>
          <div className="pr-2">
            <SessionManagerDropdown>
              <HeaderButton icon="ListRestart" />
            </SessionManagerDropdown>
          </div>
        </AnimatedConditional>
        <div className="truncate text-sm w-full font-medium text-secondary-foreground">
          {isEditing ? (
            <SessionRename sessionId={selectedSession} onSave={onSave} />
          ) : (
            sessionName
          )}
        </div>
      </div>
      {!isPlayground && selectedSession && (
        <div className="flex items-center gap-1">
          <AnimatedConditional isOpen={isSessionDropdownVisible}>
            <SessionMenuDropdown
              onRename={handleEditStart}
              onDelete={onDelete}
              onLogs={onLogs}
            >
              <HeaderButton icon="MoreVertical" />
            </SessionMenuDropdown>
          </AnimatedConditional>
          <HeaderButton
            icon={isFullscreen ? "Shrink" : "Expand"}
            onClick={toggleFullscreen}
          />
          <AnimatedConditional isOpen={isFullscreen}>
            <HeaderButton icon="X" onClick={onClose} />
          </AnimatedConditional>
          <SessionLogsModal
            sessionId={selectedSession}
            flowId={flowId}
            open={openLogsModal}
            setOpen={setOpenLogsModal}
          />
        </div>
      )}
    </div>
  );
}
