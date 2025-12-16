import React, { useEffect, useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import { cn } from "@/utils/utils";

type ChatHeaderTitleProps = {
  sessionTitle?: string;
  isEditing?: boolean;
  currentSessionId?: string;
  isFullscreen?: boolean;
  onRenameSave: (newSessionId: string) => void | Promise<void>;
  className?: string;
};

export function ChatHeaderTitle({
  sessionTitle,
  isEditing = false,
  currentSessionId,
  isFullscreen,
  onRenameSave,
  className,
}: ChatHeaderTitleProps) {
  const [value, setValue] = useState(sessionTitle ?? "");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setValue(sessionTitle ?? "");
  }, [sessionTitle]);

  useEffect(() => {
    if (isEditing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [isEditing]);

  const handleSubmit = async () => {
    const next = value.trim();
    if (!next || next === currentSessionId) return;
    await onRenameSave(next);
  };

  const handleKeyDown = async (
    event: React.KeyboardEvent<HTMLInputElement>,
  ) => {
    if (event.key === "Enter") {
      event.preventDefault();
      await handleSubmit();
    } else if (event.key === "Escape") {
      setValue(sessionTitle ?? "");
    }
  };

  return (
    <div
      className={cn(
        "flex min-w-0 items-center gap-2 text-left",
        isFullscreen ? "text-lg font-semibold" : "text-md font-semibold",
        className,
      )}
    >
      {isEditing ? (
        <Input
          ref={inputRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={handleSubmit}
          className="h-8 w-full min-w-0"
        />
      ) : (
        <div className="truncate" title={sessionTitle}>
          {sessionTitle ?? "Default Session"}
        </div>
      )}
    </div>
  );
}
