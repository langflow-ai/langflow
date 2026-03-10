import React, { useMemo, useState } from "react";
import { AnimatedConditional } from "@/components/ui/animated-close";
import useAlertStore from "@/stores/alertStore";
import { cn } from "@/utils/utils";
import { useRenameSession } from "../hooks/use-rename-session";
import { useSessionHasMessages } from "../hooks/use-session-has-messages";
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
  onRenameSession,
  onClearChat,
}: ChatHeaderProps & { sessions: string[] }) {
  // State to coordinate menu open/close
  const [sessionsDropdownOpen, setSessionsDropdownOpen] = useState(false);
  const [moreMenuOpen, setMoreMenuOpen] = useState(false);
  // Determine the title based on the current session
  const sessionTitle = useMemo(
    () => getSessionTitle(currentSessionId, currentFlowId),
    [currentSessionId, currentFlowId],
  );

  // Rename UI state — delegates actual rename to parent callback
  const handleRename = async (sessionId: string, newSessionId: string) => {
    await onRenameSession?.(sessionId, newSessionId);
  };

  const { isEditing, handleEditStart, handleEditCancel, handleEditSave } =
    useRenameSession({
      currentSessionId,
      handleRename,
      onSessionSelect,
    });
  // Keep session actions (including logs) available in fullscreen
  const isSessionDropdownVisible = true;
  const isDefaultSession = currentSessionId === currentFlowId;
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  const handleDeleteSessionInternal = () => {
    if (!currentSessionId || isDefaultSession || !currentFlowId) return;
    onDeleteSession?.(currentSessionId);
    setSuccessData({ title: "Session deleted successfully." });
  };

  const handleClearChat = () => {
    if (!currentSessionId || !isDefaultSession || !currentFlowId) return;
    onClearChat?.();
    setSuccessData({ title: "Chat cleared successfully." });
  };

  const { onMessageLogs } = useSessionMoreMenuHandlers({
    currentSessionId,
    onOpenLogs: () => setOpenLogsModal?.(true),
  });

  const hasMessages = useSessionHasMessages({
    sessionId: currentSessionId,
    flowId: currentFlowId,
  });

  const moreMenu = (
    <AnimatedConditional isOpen={isSessionDropdownVisible}>
      <SessionMoreMenu
        onRename={handleEditStart}
        onMessageLogs={onMessageLogs}
        onClearChat={handleClearChat}
        onDelete={handleDeleteSessionInternal}
        showRename={!isDefaultSession && hasMessages}
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
        "flex items-center border-b border-transparent relative overflow-visible",
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
