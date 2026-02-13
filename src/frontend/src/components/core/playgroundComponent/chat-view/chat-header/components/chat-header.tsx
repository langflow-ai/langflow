import { useMemo, useState } from "react";
import { AnimatedConditional } from "@/components/ui/animated-close";
import { useDeleteSession } from "@/controllers/API/queries/messages/use-delete-sessions";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import { cn } from "@/utils/utils";
import { clearSessionMessages } from "../../utils/message-utils";
import { useEditSessionInfo } from "../hooks/use-edit-session-info";
import { useRenameSession } from "../hooks/use-rename-session";
import { useSessionMoreMenuHandlers } from "../hooks/use-session-more-menu-handlers";
import type { ChatHeaderProps } from "../types/chat-header.types";
import { getSessionTitle } from "../utils/get-session-title";
import { ChatHeaderActions } from "./chat-header-actions";
import { ChatHeaderTitle } from "./chat-header-title";
import { ChatSessionsDropdown } from "./chat-sessions-dropdown";
import { SessionLogsModal } from "./session-logs-modal";
import { SessionMoreMenu } from "./session-more-menu";

export function ChatHeader({
  sessions,
  onNewChat,
  onSessionSelect,
  currentSessionId,
  currentFlowId,
  isFullscreen = false,
  onDeleteSession,
  className,
  onClose,
  openLogsModal,
  setOpenLogsModal,
  renameLocalSession,
}: ChatHeaderProps & { sessions: string[] }) {
  // State to coordinate menu open/close
  const [sessionsDropdownOpen, setSessionsDropdownOpen] = useState(false);
  const [moreMenuOpen, setMoreMenuOpen] = useState(false);
  // Determine the title based on the current session
  const sessionTitle = useMemo(
    () => getSessionTitle(currentSessionId, currentFlowId),
    [currentSessionId, currentFlowId],
  );

  // Session edit/delete logic
  const { handleRename, handleDelete } = useEditSessionInfo({
    flowId: currentFlowId,
    renameLocalSession,
  });

  const { isEditing, handleEditStart, handleEditCancel, handleEditSave } =
    useRenameSession({
      currentSessionId,
      handleRename,
      onSessionSelect,
    });
  const handleEditStartLogged = () => {
    handleEditStart();
  };

  const isShareablePlayground = useFlowStore((state) => state.playgroundPage);
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const isSessionDropdownVisible = true;
  const isDefaultSession = currentSessionId === currentFlowId;
  const deleteSessionMutation = useDeleteSession({});
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  const handleDeleteSessionInternal = () => {
    if (!currentSessionId || !currentFlowId) return;

    if (isShareablePlayground) {
      clearSessionMessages(currentSessionId, currentFlowId);
      if (!isDefaultSession) {
        handleDelete(currentSessionId);
        onDeleteSession?.(currentSessionId);
      }
      setSuccessData({ title: "Session deleted successfully." });
      return;
    }

    if (isDefaultSession) return;

    deleteSessionMutation.mutate(
      { sessionId: currentSessionId },
      {
        onSuccess: () => {
          clearSessionMessages(currentSessionId, currentFlowId);
          handleDelete(currentSessionId);
          onDeleteSession?.(currentSessionId);
          setSuccessData({ title: "Session deleted successfully." });
        },
        onError: () => {
          setErrorData({ title: "Error deleting session." });
        },
      },
    );
  };

  const handleClearChat = () => {
    if (!currentSessionId || !currentFlowId) return;

    if (isShareablePlayground) {
      clearSessionMessages(currentSessionId, currentFlowId);
      setSuccessData({ title: "Chat cleared successfully." });
      return;
    }

    deleteSessionMutation.mutate(
      { sessionId: currentSessionId },
      {
        onSuccess: () => {
          clearSessionMessages(currentSessionId, currentFlowId);
          setSuccessData({ title: "Chat cleared successfully." });
        },
        onError: () => {
          setErrorData({ title: "Error clearing chat." });
        },
      },
    );
  };

  const { onMessageLogs } = useSessionMoreMenuHandlers({
    currentSessionId,
    onOpenLogs: () => setOpenLogsModal?.(true),
  });

  const canRename = !isShareablePlayground && !isDefaultSession;
  const canShowLogs = !isShareablePlayground;
  const canClearChat = isShareablePlayground || isDefaultSession;
  const canDelete = isShareablePlayground || !isDefaultSession;
  const hasAnyMenuOption =
    canRename || canShowLogs || canClearChat || canDelete;

  const moreMenu = (
    <AnimatedConditional isOpen={isSessionDropdownVisible && hasAnyMenuOption}>
      <SessionMoreMenu
        onRename={handleEditStartLogged}
        onMessageLogs={onMessageLogs}
        onClearChat={handleClearChat}
        onDelete={handleDeleteSessionInternal}
        showRename={canRename}
        showMessageLogs={canShowLogs}
        showClearChat={canClearChat}
        showDelete={canDelete}
        side="bottom"
        align="end"
        sideOffset={4}
        contentClassName="z-[100] [&>div.p-1]:!h-auto [&>div.p-1]:!min-h-0"
        isVisible={true}
        disabled={isBuilding}
        tooltipContent="More options"
        tooltipSide="left"
        dataTestid="chat-header-more-menu"
        open={moreMenuOpen}
        onOpenChange={(open) => {
          setMoreMenuOpen(open);
          // Close sessions dropdown when more menu opens
          if (open) setSessionsDropdownOpen(false);
        }}
      />
    </AnimatedConditional>
  );

  return (
    <div
      className={cn(
        "flex items-center border-b border-transparent bg-background relative overflow-visible",
        "justify-between px-4 py-3",
        className,
      )}
    >
      {!isFullscreen && (
        <div className="flex items-center gap-2 flex-[2_1_0] min-w-0">
          <AnimatedConditional isOpen={isSessionDropdownVisible}>
            <ChatSessionsDropdown
              sessions={sessions}
              onNewChat={onNewChat}
              onSessionSelect={onSessionSelect}
              currentSessionId={currentSessionId}
              open={sessionsDropdownOpen}
              onOpenChange={(open) => {
                setSessionsDropdownOpen(open);
                // Close more menu when sessions dropdown opens
                if (open) setMoreMenuOpen(false);
              }}
            />
          </AnimatedConditional>
          <ChatHeaderTitle
            key={currentSessionId ?? "header-title"}
            sessionTitle={sessionTitle}
            isEditing={isEditing}
            currentSessionId={currentSessionId}
            isFullscreen={isFullscreen}
            onRenameSave={handleEditSave}
            onCancel={handleEditCancel}
          />
        </div>
      )}
      {isFullscreen && (
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <ChatHeaderTitle
            key={currentSessionId ?? "header-title-full"}
            sessionTitle={sessionTitle}
            isEditing={isEditing}
            currentSessionId={currentSessionId}
            isFullscreen={isFullscreen}
            onRenameSave={handleEditSave}
            onCancel={handleEditCancel}
          />
        </div>
      )}
      <div className="relative flex items-center shrink-0 justify-end min-h-xxs">
        <ChatHeaderActions
          isFullscreen={isFullscreen}
          onClose={onClose}
          renderPrefix={() => moreMenu}
        />
      </div>
      {!isShareablePlayground && currentSessionId && (
        <SessionLogsModal
          sessionId={currentSessionId}
          flowId={currentFlowId}
          open={openLogsModal ?? false}
          setOpen={setOpenLogsModal ?? (() => {})}
        />
      )}
    </div>
  );
}
