import React, { useMemo } from "react";
import { AnimatedConditional } from "@/components/ui/animated-close";
import { useDeleteSession } from "@/controllers/API/queries/messages/use-delete-sessions";
import { useIsMobile } from "@/hooks/use-mobile";
import useAlertStore from "@/stores/alertStore";
import { useMessagesStore } from "@/stores/messagesStore";
import { cn } from "@/utils/utils";
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
  onToggleFullscreen,
  isFullscreen = false,
  onDeleteSession,
  className,
  onClose,
  openLogsModal,
  setOpenLogsModal,
}: ChatHeaderProps & { sessions: string[] }) {
  // Determine the title based on the current session
  const sessionTitle = useMemo(
    () => getSessionTitle(currentSessionId, currentFlowId),
    [currentSessionId, currentFlowId],
  );

  // Session edit/delete logic
  const { handleRename, handleDelete } = useEditSessionInfo({
    flowId: currentFlowId,
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

  const isMobile = useIsMobile();
  // Keep session actions (including logs) available in fullscreen
  const isSessionDropdownVisible = true;
  const isDefaultSession = currentSessionId === currentFlowId;
  const deleteSessionMutation = useDeleteSession();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const deleteSessionFromStore = useMessagesStore(
    (state) => state.deleteSession,
  );

  const handleDeleteSessionInternal = () => {
    if (!currentSessionId) return;
    handleDelete(currentSessionId);
    onDeleteSession?.(currentSessionId);
  };

  const handleClearChat = () => {
    if (!currentSessionId || !isDefaultSession) return;

    deleteSessionMutation.mutate(
      { sessionId: currentSessionId },
      {
        onSuccess: () => {
          // Remove messages from store
          deleteSessionFromStore(currentSessionId);
          setSuccessData({
            title: "Chat cleared successfully.",
          });
        },
        onError: () => {
          setErrorData({
            title: "Error clearing chat.",
          });
        },
      },
    );
  };

  const { onMessageLogs } = useSessionMoreMenuHandlers({
    currentSessionId,
    onOpenLogs: () => setOpenLogsModal?.(true),
  });

  const moreMenu = (
    <AnimatedConditional isOpen={isSessionDropdownVisible}>
      <SessionMoreMenu
        onRename={handleEditStartLogged}
        onMessageLogs={onMessageLogs}
        onClearChat={handleClearChat}
        onDelete={handleDeleteSessionInternal}
        showClearChat={isDefaultSession}
        showDelete={!isDefaultSession}
        side="bottom"
        align="end"
        sideOffset={4}
        contentClassName="z-[100] [&>div.p-1]:!h-auto [&>div.p-1]:!min-h-0"
        isVisible={true}
        tooltipContent="More options"
        tooltipSide="left"
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
      <div className="relative flex items-center flex-1 justify-end min-h-xxs w-120">
        <AnimatedConditional isOpen={!isFullscreen}>
          <ChatHeaderActions
            isFullscreen={false}
            onToggleFullscreen={onToggleFullscreen}
            onClose={onClose}
            renderPrefix={() => moreMenu}
          />
        </AnimatedConditional>
        <AnimatedConditional isOpen={isFullscreen}>
          <ChatHeaderActions
            isFullscreen={true}
            onToggleFullscreen={onToggleFullscreen}
            onClose={onClose}
          />
        </AnimatedConditional>
      </div>
      {currentSessionId && (
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
