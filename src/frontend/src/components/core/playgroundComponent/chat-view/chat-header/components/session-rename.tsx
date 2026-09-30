import type React from "react";
import { useEffect, useRef, useState } from "react";
import { Input } from "@/components/ui/input";

interface SessionRenameProps {
  sessionId: string;
  onSave: (newSessionId: string) => void;
  onDone?: () => void;
}

// Controlled inline rename; closes on blur/Enter/Escape and auto-focuses/selects.
export const SessionRename: React.FC<SessionRenameProps> = ({
  sessionId,
  onSave,
  onDone,
}) => {
  const [value, setValue] = useState(sessionId);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // Defer focus to ensure the element is mounted and avoid immediate blur.
    const id = window.setTimeout(() => {
      inputRef.current?.focus();
      inputRef.current?.select();
    }, 0);
    return () => window.clearTimeout(id);
  }, [sessionId]);

  const commit = () => {
    const trimmed = value.trim();
    if (!trimmed || trimmed === sessionId) {
      setValue(sessionId);
      onDone?.();
      return;
    }
    onSave(trimmed);
    onDone?.();
  };

  const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    e.stopPropagation();
    commit();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      e.stopPropagation();
      commit();
    }
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      setValue(sessionId);
      onDone?.();
    }
  };

  return (
    <Input
      data-testid="session-rename-input"
      ref={inputRef}
      value={value}
      onChange={(e) => setValue(e.target.value)}
      className="h-8 text-sm border border-border p-2 w-full bg-background focus-visible:ring-1 focus-visible:ring-ring focus-visible:outline-none"
      onBlur={handleBlur}
      onKeyDown={handleKeyDown}
    />
  );
};
