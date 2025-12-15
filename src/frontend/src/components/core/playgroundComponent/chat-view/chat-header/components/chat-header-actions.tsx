import React from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";

interface ChatHeaderActionsProps {
  isFullscreen: boolean;
  onToggleFullscreen?: () => void;
  onClose?: () => void;
}

export function ChatHeaderActions({
  isFullscreen,
  onToggleFullscreen,
  onClose,
}: ChatHeaderActionsProps) {
  if (!onToggleFullscreen) {
    return null;
  }

  return (
    <div className={cn("flex items-center gap-1 justify-end")}>
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
  );
}
