import React, { useEffect, useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import { cn } from "@/utils/utils";

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
  const [value, setValue] = useState(sessionTitle ?? "");
  const inputRef = useRef<HTMLInputElement>(null);
  const [hasFocused, setHasFocused] = useState(false);

  useEffect(() => {
    setValue(sessionTitle ?? "");
  }, [sessionTitle]);

  useEffect(() => {
    if (isEditing) {
      inputRef.current?.focus();
      inputRef.current?.select();
      setHasFocused(false);
    }
  }, [isEditing]);

  const commit = async () => {
    const next = value.trim();
    // If unchanged or empty, just exit edit mode
    if (!next || next === currentSessionId || next === sessionTitle?.trim()) {
      onCancel?.();
      setValue(sessionTitle ?? "");
      return;
    }
    await onRenameSave(next);
    onCancel?.();
  };

  const handleKeyDown = async (
    event: React.KeyboardEvent<HTMLInputElement>,
  ) => {
    if (event.key === "Enter") {
      event.preventDefault();
      await commit();
    } else if (event.key === "Escape") {
      setValue(sessionTitle ?? "");
      onCancel?.();
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
          onFocus={() => setHasFocused(true)}
          onBlur={() => {
            if (!hasFocused) return;
            void commit();
          }}
          className="h-8 w-full min-w-0"
        />
      ) : (
        <div
          className="truncate text-[13px] font-medium leading-4 text-[#CCC]"
          title={sessionTitle}
        >
          {sessionTitle ?? "Default Session"}
        </div>
      )}
    </div>
  );
}
