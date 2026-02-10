import React from "react";
import { cn } from "@/utils/utils";
import { SessionRename } from "./session-rename";

type ChatHeaderTitleProps = {
  sessionTitle?: string;
  isEditing?: boolean;
  currentSessionId?: string;
  isFullscreen?: boolean;
  onRenameSave: (newSessionId: string) => void | Promise<void>;
  onCancel?: () => void;
  className?: string;
};

export function ChatHeaderTitle({
  sessionTitle,
  isEditing = false,
  currentSessionId,
  isFullscreen,
  onRenameSave,
  onCancel,
  className,
}: ChatHeaderTitleProps) {
  const displayTitle = sessionTitle ?? "Default Session";

  return (
    <div
      className={cn(
        "flex min-w-0 items-center gap-2 text-left",
        isFullscreen ? "text-lg font-semibold" : "text-md font-semibold",
        className,
      )}
    >
      {isEditing ? (
        <SessionRename
          sessionId={currentSessionId ?? ""}
          onSave={(val) => {
            void onRenameSave(val);
          }}
          onDone={onCancel}
        />
      ) : (
        <div className="truncate text-mmd text-foreground" title={displayTitle}>
          {displayTitle}
        </div>
      )}
    </div>
  );
}
