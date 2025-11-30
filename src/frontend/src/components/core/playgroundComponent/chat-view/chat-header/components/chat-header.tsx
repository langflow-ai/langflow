import type { AxiosError } from "axios";
import React, { useCallback, useMemo, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select-custom";
import { useUpdateSessionName } from "@/controllers/API/queries/messages/use-rename-session";
import { cn } from "@/utils/utils";
import type { ChatHeaderProps } from "../types/chat-header.types";
import { ChatSessionsDropdown } from "./chat-sessions-dropdown";
import { SessionLogsModal } from "./session-logs-modal";
import { SessionRename } from "./session-rename";

// Constants
const TITLE_STYLES =
  "flex flex-col justify-center flex-[1_0_0] self-stretch text-[#CCC] text-sm font-medium leading-4";
const TITLE_FONT_FAMILY = { fontFamily: "Inter" } as const;
const MORE_MENU_SIDE_OFFSET = 4;
const MORE_MENU_Z_INDEX = 100;

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
  const sessionTitle = useMemo(() => {
    if (!currentSessionId) {
      return "Chat";
    }
    if (currentSessionId === currentFlowId) {
      return "Default Session";
    }
    return currentSessionId;
  }, [currentSessionId, currentFlowId]);

  // Rename functionality
  const [isEditing, setIsEditing] = useState(false);
  const [selectValue, setSelectValue] = useState("");
  const [openLogsModal, setOpenLogsModal] = useState(false);
  const { mutate: updateSessionName } = useUpdateSessionName();

  const handleRename = useCallback(() => {
    console.log("handleRename called, currentSessionId:", currentSessionId);
    if (!currentSessionId) {
      console.log("Cannot rename: no session");
      return;
    }
    // Allow renaming even the default session
    console.log("Setting isEditing to true");
    setIsEditing(true);
  }, [currentSessionId]);
  const handleRenameSave = useCallback(
    (newSessionId: string) => {
      if (
        !currentSessionId ||
        !newSessionId.trim() ||
        newSessionId.trim() === currentSessionId
      ) {
        setIsEditing(false);
        return;
      }

      const trimmedNewId = newSessionId.trim();

      // Optimistically update the UI immediately
      setIsEditing(false);
      if (onSessionSelect) {
        onSessionSelect(trimmedNewId);
      }

      // Then update via API in the background
      updateSessionName(
        {
          old_session_id: currentSessionId,
          new_session_id: trimmedNewId,
        },
        {
          onSuccess: () => {
            // Already updated optimistically, just ensure state is correct
            if (onSessionSelect) {
              onSessionSelect(trimmedNewId);
            }
          },
          onError: (error: unknown) => {
            const axiosError = error as AxiosError;
            // Check if it's a "no messages found" error
            if (
              axiosError?.response?.data &&
              typeof axiosError.response.data === "object" &&
              "detail" in axiosError.response.data &&
              typeof axiosError.response.data.detail === "string" &&
              axiosError.response.data.detail.includes("No messages found")
            ) {
              // Session doesn't exist in database but exists in sessionStorage
              // The optimistic update already handled this, so we're good
            } else {
              // For other errors, revert to the old session ID
              if (onSessionSelect) {
                onSessionSelect(currentSessionId);
              }
            }
          },
        },
      );
    },
    [currentSessionId, updateSessionName, onSessionSelect],
  );

  const handleMessageLogs = useCallback(() => {
    // Open message logs modal for the current session
    console.log(
      "handleMessageLogs called, currentSessionId:",
      currentSessionId,
    );
    if (currentSessionId) {
      setOpenLogsModal(true);
    }
  }, [currentSessionId]);

  const handleDelete = useCallback(() => {
    console.log(
      "handleDelete called, currentSessionId:",
      currentSessionId,
      "onDeleteSession:",
      !!onDeleteSession,
    );
    if (currentSessionId && onDeleteSession) {
      onDeleteSession(currentSessionId);
    } else {
      console.log("Cannot delete: missing currentSessionId or onDeleteSession");
    }
  }, [currentSessionId, onDeleteSession]);

  const titleElement = useMemo(() => {
    if (isEditing && currentSessionId) {
      return (
        <div className={cn("flex items-center", isFullscreen ? "" : "flex-1")}>
          <SessionRename
            sessionId={currentSessionId}
            onSave={handleRenameSave}
          />
        </div>
      );
    }
    return (
      <h2
        className={cn(TITLE_STYLES, isFullscreen && "flex-[0_0_auto]")}
        style={TITLE_FONT_FAMILY}
      >
        {sessionTitle}
      </h2>
    );
  }, [
    isEditing,
    currentSessionId,
    sessionTitle,
    handleRenameSave,
    isFullscreen,
  ]);

  return (
    <div
      className={cn(
        "flex items-center border-b border-transparent p-4 bg-background relative overflow-visible",
        isFullscreen && "justify-center",
        !isFullscreen && "justify-between",
        className,
      )}
    >
      {!isFullscreen && (
        <div className="flex items-center gap-2">
          <ChatSessionsDropdown
            onNewChat={onNewChat}
            onSessionSelect={onSessionSelect}
            currentSessionId={currentSessionId}
          />
          {titleElement}
        </div>
      )}
      {isFullscreen && titleElement}
      {onToggleFullscreen && (
        <div
          className={cn(
            "flex items-center gap-2",
            isFullscreen && "absolute right-4",
          )}
        >
          {!isFullscreen && (
            <div className="relative">
              <Select
                value={selectValue}
                onValueChange={(value) => {
                  console.log("Select value changed:", value);
                  setSelectValue(value);
                  // Execute the action immediately
                  switch (value) {
                    case "rename":
                      console.log("Calling handleRename");
                      handleRename();
                      break;
                    case "messageLogs":
                      console.log("Calling handleMessageLogs");
                      handleMessageLogs();
                      break;
                    case "delete":
                      console.log("Calling handleDelete");
                      handleDelete();
                      break;
                  }
                  // Reset after a short delay to allow the select to close
                  setTimeout(() => {
                    setSelectValue("");
                  }, 100);
                }}
              >
                <ShadTooltip
                  styleClasses="z-50"
                  side="left"
                  content="More options"
                >
                  <SelectTrigger
                    className="h-8 w-8 border-none bg-transparent p-2 focus:ring-0"
                    aria-label="More options"
                    aria-haspopup="true"
                    onClick={(e) => {
                      e.stopPropagation();
                      console.log("Select trigger clicked");
                    }}
                  >
                    <ForwardedIconComponent
                      name="MoreVertical"
                      className="h-4 w-4"
                      aria-hidden="true"
                    />
                  </SelectTrigger>
                </ShadTooltip>
                <SelectContent
                  side="bottom"
                  align="end"
                  sideOffset={MORE_MENU_SIDE_OFFSET}
                  className="p-0 z-[100] [&>div.p-1]:!h-auto [&>div.p-1]:!min-h-0"
                >
                  <SelectItem
                    value="rename"
                    className="cursor-pointer px-3 py-2 focus:bg-muted"
                  >
                    <div className="flex items-center">
                      <ForwardedIconComponent
                        name="SquarePen"
                        className="mr-2 h-4 w-4"
                      />
                      Rename
                    </div>
                  </SelectItem>
                  <SelectItem
                    value="messageLogs"
                    className="cursor-pointer px-3 py-2 focus:bg-muted"
                  >
                    <div className="flex items-center">
                      <ForwardedIconComponent
                        name="Scroll"
                        className="mr-2 h-4 w-4"
                      />
                      Message logs
                    </div>
                  </SelectItem>
                  <SelectItem
                    value="delete"
                    className="cursor-pointer px-3 py-2 focus:bg-muted"
                  >
                    <div className="flex items-center text-status-red hover:text-status-red">
                      <ForwardedIconComponent
                        name="Trash2"
                        className="mr-2 h-4 w-4"
                      />
                      Delete
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}
          <button
            type="button"
            onClick={onToggleFullscreen}
            className="p-2 hover:bg-accent rounded transition-colors"
            title={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
            aria-label={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
          >
            <ForwardedIconComponent
              name={isFullscreen ? "Shrink" : "Expand"}
              className="h-4 w-4"
              aria-hidden="true"
            />
          </button>
          {isFullscreen && onClose && (
            <button
              type="button"
              onClick={onClose}
              className="p-2 hover:bg-accent rounded transition-colors"
              title="Close and go back to flow"
              aria-label="Close and go back to flow"
            >
              <ForwardedIconComponent
                name="X"
                className="h-4 w-4"
                aria-hidden="true"
              />
            </button>
          )}
        </div>
      )}
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
