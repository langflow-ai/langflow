import React, { useMemo } from "react";
import { AnimatedConditional } from "@/components/ui/animated-close";
import { cn } from "@/utils/utils";
import { useChatHeaderRename } from "../hooks/use-chat-header-rename";
import { useChatHeaderSessionActions } from "../hooks/use-chat-header-session-actions";
import type { ChatHeaderProps } from "../types/chat-header.types";
import { getSessionTitle } from "../utils/get-session-title";
import { ChatHeaderActions } from "./chat-header-actions";
import { ChatHeaderTitle } from "./chat-header-title";
import { ChatSessionsDropdown } from "./chat-sessions-dropdown";
import { SessionLogsModal } from "./session-logs-modal";
import { SessionMoreMenu } from "./session-more-menu";

export function ChatHeader({
  onNewChat,
  onSessionSelect,
  currentSessionId,
  currentFlowId,
  onToggleFullscreen,
  isFullscreen = false,
  onDeleteSession,
  className,
  onClose,
}: ChatHeaderProps) {
  // Determine the title based on the current session
  const sessionTitle = useMemo(
    () => getSessionTitle(currentSessionId, currentFlowId),
    [currentSessionId, currentFlowId],
  );

  // Rename functionality
  const { isEditing, handleRename, handleRenameSave } = useChatHeaderRename({
    currentSessionId,
    onSessionSelect,
  });

  // Session actions (message logs, delete)
  const { openLogsModal, setOpenLogsModal, handleMessageLogs, handleDelete } =
    useChatHeaderSessionActions({
      currentSessionId,
      onDeleteSession,
    });

  return (
    <div
      className={cn(
        "flex items-center border-b border-transparent p-4 bg-background relative overflow-visible",
        isFullscreen ? "justify-between" : "justify-between",
        className,
      )}
    >
      {!isFullscreen && (
        <div className="flex items-center gap-2 flex-[2_1_0] min-w-0">
          <ChatSessionsDropdown
            onNewChat={onNewChat}
            onSessionSelect={onSessionSelect}
            currentSessionId={currentSessionId}
          />
          <ChatHeaderTitle
            sessionTitle={sessionTitle}
            isEditing={isEditing}
            currentSessionId={currentSessionId}
            isFullscreen={isFullscreen}
            onRenameSave={handleRenameSave}
          />
        </div>
      )}
      {isFullscreen && (
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <ChatHeaderTitle
            sessionTitle={sessionTitle}
            isEditing={isEditing}
            currentSessionId={currentSessionId}
            isFullscreen={isFullscreen}
            onRenameSave={handleRenameSave}
          />
        </div>
      )}
      <div className="relative flex items-center flex-1 justify-end min-h-[32px] w-[120px]">
        <AnimatedConditional
          isOpen={!isFullscreen}
          className="absolute right-0 top-1/2 flex h-full w-full -translate-y-1/2 items-center justify-end gap-1"
        >
          <ChatHeaderActions
            isFullscreen={false}
            onToggleFullscreen={onToggleFullscreen}
            onClose={onClose}
            renderPrefix={() => (
              <SessionMoreMenu
                onRename={handleRename}
                onMessageLogs={handleMessageLogs}
                onDelete={handleDelete}
                side="bottom"
                align="end"
                sideOffset={4}
                contentClassName="z-[100] [&>div.p-1]:!h-auto [&>div.p-1]:!min-h-0"
                isVisible={true}
                tooltipContent="More options"
                tooltipSide="left"
              />
            )}
          />
        </AnimatedConditional>
        <AnimatedConditional
          isOpen={isFullscreen}
          className="absolute right-0 top-1/2 flex h-full w-full -translate-y-1/2 items-center justify-end gap-1"
        >
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
          open={openLogsModal}
          setOpen={setOpenLogsModal}
        />
      )}
    </div>
  );
}
