import React from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";

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

  const actionButtonClasses =
    "h-8 w-8 p-2 text-muted-foreground hover:text-foreground hover:bg-accent rounded transition-colors overflow-hidden no-focus-visible";

  return (
    <div className="relative flex items-center gap-2 w-20 justify-end">
      {renderPrefix && <div className="shrink-0">{renderPrefix()}</div>}
      <Button
        onClick={onToggleFullscreen}
        variant="ghost"
        size="icon"
        className={actionButtonClasses}
        title={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
        aria-label={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
      >
        <ForwardedIconComponent
          name={isFullscreen ? "Shrink" : "Expand"}
          className="h-4 w-4"
          aria-hidden="true"
        />
      </Button>
      {isFullscreen && onClose && (
        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          className={actionButtonClasses}
          title="Close and go back to flow"
          aria-label="Close and go back to flow"
        >
          <ForwardedIconComponent
            name="X"
            className="h-4 w-4"
            aria-hidden="true"
          />
        </Button>
      )}
    </div>
  );
}
