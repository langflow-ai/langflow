import React from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";

interface ChatHeaderActionsProps {
  onNewChat?: () => void;
}

export function ChatHeaderActions({ onNewChat }: ChatHeaderActionsProps) {
  if (!onNewChat) return null;

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={onNewChat}
        className="p-2 hover:bg-accent rounded transition-colors"
        aria-label="New chat"
      >
        <ForwardedIconComponent name="Plus" className="h-4 w-4" />
      </button>
    </div>
  );
}
