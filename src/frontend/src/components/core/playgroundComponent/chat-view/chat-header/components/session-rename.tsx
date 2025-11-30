import type React from "react";
import { useEffect, useRef, useState } from "react";
import { Input } from "@/components/ui/input";

interface SessionRenameProps {
  sessionId?: string;
  onSave?: (newSessionId: string) => void;
}

export const SessionRename = ({ sessionId, onSave }: SessionRenameProps) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isInitialMount, setIsInitialMount] = useState(true);
  const savedRef = useRef(false); // Track if we've already saved to prevent double-saving

  useEffect(() => {
    // Focus and select text when component mounts
    const focusInput = () => {
      if (inputRef.current) {
        inputRef.current.focus();
        inputRef.current.select();
      }
    };

    // Use requestAnimationFrame to ensure DOM is ready
    const rafId = requestAnimationFrame(() => {
      setTimeout(() => {
        focusInput();
        // Allow blur after a short delay to prevent immediate blur from Select closing
        setTimeout(() => {
          setIsInitialMount(false);
        }, 100);
      }, 0);
    });

    return () => {
      cancelAnimationFrame(rafId);
      savedRef.current = false; // Reset on unmount
    };
  }, []);

  const handleSave = (value: string) => {
    // Prevent double-saving
    if (savedRef.current) {
      return;
    }
    savedRef.current = true;
    const trimmedValue = value.trim();
    onSave?.(trimmedValue);
  };

  const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    e.stopPropagation();
    // Don't save if we just mounted (prevents immediate blur from Select closing)
    if (isInitialMount) {
      return;
    }
    handleSave(e.currentTarget.value);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      e.stopPropagation();
      // Blur the input to trigger save
      e.currentTarget.blur();
      handleSave(e.currentTarget.value);
    } else if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      // Cancel rename by calling onSave with original value
      savedRef.current = true; // Mark as saved to prevent blur from also saving
      e.currentTarget.blur();
      onSave?.(sessionId || "");
    }
  };

  return (
    <Input
      ref={inputRef}
      defaultValue={sessionId}
      autoFocus
      className="h-8 text-sm border-none p-0 w-full"
      style={{ fontFamily: "Inter" }}
      onBlur={handleBlur}
      onKeyDown={handleKeyDown}
    />
  );
};
