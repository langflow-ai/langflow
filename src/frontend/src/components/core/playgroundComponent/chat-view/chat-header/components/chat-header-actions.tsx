import React from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";

interface ChatHeaderActionsProps {
  isFullscreen: boolean;
  onToggleFullscreen?: () => void;
  onClose?: () => void;
  renderPrefix?: () => React.ReactNode;
}

export function ChatHeaderActions({
  isFullscreen,
  onToggleFullscreen,
  onClose,
  renderPrefix,
}: ChatHeaderActionsProps) {
  if (!onToggleFullscreen) {
    return null;
  }

  return (
    <div
      className={cn("relative flex items-center gap-2 w-[64px] justify-end")}
    >
      {renderPrefix && <div className="shrink-0">{renderPrefix()}</div>}
      <button
        type="button"
        onClick={onToggleFullscreen}
        className="relative p-2 hover:bg-accent rounded transition-colors overflow-hidden"
        title={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
        aria-label={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
      >
        <span
          className={cn(
            "absolute inset-0 flex items-center justify-center",
            isFullscreen ? "opacity-0" : "opacity-100 translate-x-0",
          )}
          aria-hidden="true"
        >
          <ForwardedIconComponent name="Expand" className="h-4 w-4" />
        </span>
        <span
          className={cn(
            "absolute inset-0 flex items-center justify-center",
            isFullscreen ? "opacity-100" : "opacity-0",
          )}
          aria-hidden="true"
        >
          <ForwardedIconComponent name="Shrink" className="h-4 w-4" />
        </span>
      </button>
      {isFullscreen && onClose && (
        <button
          type="button"
          onClick={onClose}
          className="p-2 hover:bg-accent rounded transition-colors overflow-hidden"
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
