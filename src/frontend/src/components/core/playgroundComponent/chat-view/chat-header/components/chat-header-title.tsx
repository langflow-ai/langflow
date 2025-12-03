import React from "react";
import { cn } from "@/utils/utils";
import { SessionRename } from "./session-rename";

const TITLE_STYLES =
  "flex flex-col justify-center flex-[1_0_0] self-stretch text-[#CCC] text-sm font-medium leading-4";
const TITLE_FONT_FAMILY = { fontFamily: "Inter" } as const;

interface ChatHeaderTitleProps {
  sessionTitle: string;
  isEditing: boolean;
  currentSessionId?: string;
  isFullscreen: boolean;
  onRenameSave: (newSessionId: string) => void;
}

export function ChatHeaderTitle({
  sessionTitle,
  isEditing,
  currentSessionId,
  isFullscreen,
  onRenameSave,
}: ChatHeaderTitleProps) {
  if (isEditing && currentSessionId) {
    return (
      <div className={cn("flex items-center", isFullscreen ? "" : "min-w-0")}>
        <SessionRename sessionId={currentSessionId} onSave={onRenameSave} />
      </div>
    );
  }

  return (
    <h2
      className={cn(
        TITLE_STYLES,
        isFullscreen ? "flex-1 text-left min-w-0 truncate" : "min-w-0 truncate",
      )}
      style={TITLE_FONT_FAMILY}
    >
      {sessionTitle}
    </h2>
  );
}
