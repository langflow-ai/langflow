import React, { useMemo, useState } from "react";
import { AnimatedConditional } from "@/components/ui/animated-close";
import { useDeleteSession } from "@/controllers/API/queries/messages/use-delete-sessions";
import { useIsMobile } from "@/hooks/use-mobile";
import useAlertStore from "@/stores/alertStore";
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
  onToggleFullscreen,
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

  const isMobile = useIsMobile();
  // Keep session actions (including logs) available in fullscreen
  const isSessionDropdownVisible = true;
  const isDefaultSession = currentSessionId === currentFlowId;
  const deleteSessionMutation = useDeleteSession({});
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  const handleDeleteSessionInternal = () => {
    if (!currentSessionId || isDefaultSession || !currentFlowId) return;

    deleteSessionMutation.mutate(
      { sessionId: currentSessionId },
      {
        onSuccess: () => {
          // Clear messages from React Query cache
          clearSessionMessages(currentSessionId, currentFlowId);
          // Call the delete handler to update session list and selected session
          handleDelete(currentSessionId);
          // Call the parent callback
          onDeleteSession?.(currentSessionId);
          setSuccessData({
            title: "Session deleted successfully.",
          });
        },
        onError: () => {
          setErrorData({
            title: "Error deleting session.",
          });
        },
      },
    );
  };

  const handleClearChat = () => {
    if (!currentSessionId || !isDefaultSession || !currentFlowId) return;

    deleteSessionMutation.mutate(
      { sessionId: currentSessionId },
      {
        onSuccess: () => {
          // Clear messages from React Query cache
          clearSessionMessages(currentSessionId, currentFlowId);
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
        showRename={!isDefaultSession}
        showClearChat={isDefaultSession}
        showDelete={!isDefaultSession}
        side="bottom"
        align="end"
        sideOffset={4}
        contentClassName="z-[100] [&>div.p-1]:!h-auto [&>div.p-1]:!min-h-0"
        isVisible={true}
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
      <div className="relative flex items-center flex-1 justify-end min-h-xxs">
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
