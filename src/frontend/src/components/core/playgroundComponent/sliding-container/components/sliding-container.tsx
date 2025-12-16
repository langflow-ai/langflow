import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/utils/utils";

const DEFAULT_WIDTH = 400;
const DEFAULT_DURATION = 0.3;

interface SlidingContainerProps {
  isOpen: boolean;
  children: React.ReactNode;
  className?: string;
  width?: number;
  onWidthChange?: (width: number) => void;
  resizable?: boolean;
  duration?: number;
  isFullscreen?: boolean;
}

export function SlidingContainer({
  isOpen,
  children,
  className,
  width = DEFAULT_WIDTH,
  onWidthChange,
  resizable = false,
  duration = DEFAULT_DURATION,
  isFullscreen = false,
}: SlidingContainerProps) {
  const [isResizing, setIsResizing] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (!resizable || !isOpen) return;
      e.preventDefault();
      setIsResizing(true);
    },
    [resizable, isOpen],
  );

  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!onWidthChange) return;
      const newWidth = window.innerWidth - e.clientX;
      onWidthChange(newWidth);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isResizing, onWidthChange]);

  const fullscreenWidth = "100%";
  const actualWidth = isFullscreen
    ? fullscreenWidth
    : isOpen
      ? `${width}px`
      : "0px";

  return (
    <div
      ref={containerRef}
      className={cn(
        // Sync with outer overlay: animate width only, match easing and duration.
        "relative h-full overflow-hidden transition-[width] ease",
        isResizing && "select-none",
        className,
      )}
      style={{
        width: actualWidth,
        transitionDuration: isResizing ? "0ms" : `${duration}ms`,
      }}
    >
      {resizable && isOpen && !isFullscreen && (
        <div
          onMouseDown={handleMouseDown}
          className={cn(
            "absolute left-0 top-0 z-10 h-full w-1 cursor-col-resize bg-transparent hover:bg-primary/20 transition-colors",
            isResizing && "bg-primary/30",
          )}
          style={{ touchAction: "none" }}
          aria-label="Resize panel"
        />
      )}
      <div className="h-full w-full">{children}</div>
    </div>
  );
}
