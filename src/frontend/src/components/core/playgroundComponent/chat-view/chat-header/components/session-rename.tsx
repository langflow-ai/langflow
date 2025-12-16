import React, { useEffect, useRef, useState } from "react";
import { Input } from "@/components/ui/input";

type SessionRenameProps = {
  sessionId: string;
  onSave: (newSessionId: string) => void | Promise<void>;
};

//Inline session rename control used inside the chat header.

export function SessionRename({ sessionId, onSave }: SessionRenameProps) {
  const [value, setValue] = useState(sessionId);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setValue(sessionId);
  }, [sessionId]);

  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  const handleSave = async () => {
    const trimmed = value.trim();
    if (!trimmed || trimmed === sessionId) return;
    await onSave(trimmed);
  };

  const handleKeyDown = async (
    event: React.KeyboardEvent<HTMLInputElement>,
  ) => {
    if (event.key === "Enter") {
      event.preventDefault();
      await handleSave();
    }
    if (event.key === "Escape") {
      setValue(sessionId);
    }
  };

  return (
    <Input
      ref={inputRef}
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onKeyDown={handleKeyDown}
      onBlur={handleSave}
      className="h-8 w-full min-w-0"
    />
  );
}
