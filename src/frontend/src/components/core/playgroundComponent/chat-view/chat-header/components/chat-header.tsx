import React, { useMemo, useState } from "react";
import { AnimatedConditional } from "@/components/ui/animated-close";
import { useIsMobile } from "@/hooks/use-mobile";
import { cn } from "@/utils/utils";
import { useEditSessionInfo } from "../hooks/use-edit-session-info";
import { useRenameSession } from "../hooks/use-rename-session";
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
  const { isEditing, handleEditSave, handleEditStart } = useRenameSession({
    currentSessionId,
    handleRename,
    onSessionSelect,
  });

  const [openLogsModal, setOpenLogsModal] = useState(false);
  const isMobile = useIsMobile();
  const isSessionDropdownVisible = !isFullscreen || isMobile;
  const handleMessageLogs = () => {
    if (currentSessionId) {
      setOpenLogsModal(true);
    }
  };

  const handleDeleteSessionInternal = () => {
    if (!currentSessionId) return;
    handleDelete(currentSessionId);
    onDeleteSession?.(currentSessionId);
  };

  const moreMenu = (
    <AnimatedConditional isOpen={isSessionDropdownVisible}>
      <SessionMoreMenu
        onRename={handleEditStart}
        onMessageLogs={handleMessageLogs}
        onDelete={handleDeleteSessionInternal}
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
        "flex items-center border-b border-transparent p-4 bg-background relative overflow-visible",
        "justify-between",
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
            sessionTitle={sessionTitle}
            isEditing={isEditing}
            currentSessionId={currentSessionId}
            isFullscreen={isFullscreen}
            onRenameSave={handleEditSave}
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
            onRenameSave={handleEditSave}
          />
        </div>
      )}
      <div className="relative flex items-center flex-1 justify-end min-h-[32px] w-[120px]">
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
          open={openLogsModal}
          setOpen={setOpenLogsModal}
        />
      )}
    </div>
  );
}
