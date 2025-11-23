import type React from "react";
import { Input } from "@/components/ui/input";

interface SessionRenameProps {
  sessionId?: string;
  onSave?: (newSessionId: string) => void;
}

export const SessionRename = ({ sessionId, onSave }: SessionRenameProps) => {
  const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    e.stopPropagation();
    onSave?.(e.currentTarget.value);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.stopPropagation();
      onSave?.(e.currentTarget.value);
    }
  };

  return (
    <Input
      defaultValue={sessionId}
      autoFocus
      className="h-8 text-sm border-none p-0 w-full"
      onBlur={handleBlur}
      onKeyDown={handleKeyDown}
    />
  );
};
