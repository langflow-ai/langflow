"use client";

import { motion } from "framer-motion";
import { PanelLeftOpen, PanelRightOpen } from "lucide-react";
import * as React from "react";
import { useHotkeys } from "react-hotkeys-hook";
import isWrappedWithClass from "../../pages/FlowPage/components/PageComponent/utils/is-wrapped-with-class";
import { cn } from "../../utils/utils";
import { AnimatedConditional } from "./animated-close";
import { Button } from "./button";

const SIMPLE_SIDEBAR_WIDTH = "400px";
const MIN_SIDEBAR_WIDTH = 200;
const MAX_SIDEBAR_WIDTH = 800;

type SimpleSidebarContext = {
  open: boolean;
  setOpen: (open: boolean) => void;
  toggleSidebar: () => void;
  width: number;
  setWidth: (width: number) => void;
  isResizing: boolean;
  setIsResizing: (isResizing: boolean) => void;
  fullscreen: boolean;
};

const SimpleSidebarContext = React.createContext<SimpleSidebarContext | null>(
  null,
);

function useSimpleSidebar() {
  const context = React.useContext(SimpleSidebarContext);
  if (!context) {
    throw new Error(
      "useSimpleSidebar must be used within a SimpleSidebarProvider.",
    );
  }

  return context;
}

const SimpleSidebarProvider = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<"div"> & {
    defaultOpen?: boolean;
    open?: boolean;
    onOpenChange?: (open: boolean) => void;
    width?: string;
    shortcut?: string;
    minWidth?: number; // 0 to 1, percentage of parent width
    maxWidth?: number; // 0 to 1, percentage of parent width
    onMaxWidth?: (attemptedWidth: number, maxWidth: number) => void;
    fullscreen?: boolean;
  }
>(
  (
    {
      defaultOpen = false,
      open: openProp,
      onOpenChange: setOpenProp,
      className,
      style,
      children,
      width = SIMPLE_SIDEBAR_WIDTH,
      shortcut,
      minWidth = 0.1, // 10% of parent width
      maxWidth = 0.8, // 80% of parent width
      onMaxWidth,
      fullscreen = false,
      ...props
    },
    ref,
  ) => {
    // This is the internal state of the sidebar.
    // We use openProp and setOpenProp for control from outside the component.
    const [_open, _setOpen] = React.useState(defaultOpen);
    const [_width, _setWidth] = React.useState(
      typeof width === "string" ? parseInt(width.replace("px", "")) : width,
    );
    const [_isResizing, _setIsResizing] = React.useState(false);
    const [_parentWidth, _setParentWidth] = React.useState(10000);
    const [_wasDragged, _setWasDragged] = React.useState(false);

    // Internal ref for tracking parent width
    const internalRef = React.useRef<HTMLDivElement>(null);

    const open = openProp ?? _open;
    const setOpen = React.useCallback(
      (value: boolean | ((value: boolean) => boolean)) => {
        if (setOpenProp) {
          return setOpenProp?.(
            typeof value === "function" ? value(open) : value,
          );
        }

        _setOpen(value);
      },
      [setOpenProp, open],
    );

    const setWidth = React.useCallback(
      (newWidth: number) => {
        _setWasDragged(true);
        const minWidthPx = _parentWidth * minWidth;
        const maxWidthPx = _parentWidth * maxWidth;

        // Fallback to absolute constraints if parent width is not available
        const minConstraint = _parentWidth > 0 ? minWidthPx : MIN_SIDEBAR_WIDTH;
        const maxConstraint = _parentWidth > 0 ? maxWidthPx : MAX_SIDEBAR_WIDTH;

        // Check if user is trying to resize beyond max width
        if (newWidth > maxConstraint && onMaxWidth) {
          onMaxWidth(newWidth, maxConstraint);
        }

        const constrainedWidth = Math.min(
          Math.max(newWidth, minConstraint),
          maxConstraint,
        );
        _setWidth(constrainedWidth);
      },
      [_parentWidth, minWidth, maxWidth, onMaxWidth],
    );

    // Helper to toggle the sidebar.
    const toggleSidebar = React.useCallback(() => {
      return setOpen((prev) => !prev);
    }, [setOpen]);

    // Reset width and isResizing when fullscreen is true (unless user dragged)
    React.useEffect(() => {
      if (fullscreen) {
        if (!_wasDragged) {
          _setWidth(
            typeof width === "string"
              ? parseInt(width.replace("px", ""))
              : width,
          );
        }
        _setIsResizing(false);
      }
    }, [fullscreen, width, _wasDragged]);

    // Track parent width using ResizeObserver
    React.useEffect(() => {
      const element = internalRef.current;
      if (!element) return;

      const resizeObserver = new ResizeObserver((entries) => {
        for (const entry of entries) {
          _setParentWidth(entry.contentRect.width);
        }
      });

      resizeObserver.observe(element);

      // Initial measurement
      _setParentWidth(element.getBoundingClientRect().width);

      return () => {
        resizeObserver.disconnect();
      };
    }, []);

    const contextValue = React.useMemo<SimpleSidebarContext>(
      () => ({
        open,
        setOpen,
        toggleSidebar,
        width: _width,
        setWidth,
        isResizing: _isResizing,
        setIsResizing: _setIsResizing,
        fullscreen,
      }),
      [open, setOpen, toggleSidebar, _width, setWidth, _isResizing, fullscreen],
    );

    // Register hotkey if provided
    useHotkeys(
      shortcut ?? "",
      (e: KeyboardEvent) => {
        if (!shortcut) return;
        if (isWrappedWithClass(e, "noflow")) return;
        e.preventDefault();
        toggleSidebar();
      },
      {
        preventDefault: true,
        enabled: !!shortcut,
      },
    );

    // Combine refs to track both forwarded ref and internal ref
    const combinedRef = React.useCallback(
      (node: HTMLDivElement | null) => {
        // Set our internal ref
        (internalRef as React.MutableRefObject<HTMLDivElement | null>).current =
          node;

        // Handle forwarded ref
        if (typeof ref === "function") {
          ref(node);
        } else if (ref) {
          try {
            (ref as React.MutableRefObject<HTMLDivElement | null>).current =
              node;
          } catch {
            // Ignore read-only ref errors
          }
        }
      },
      [ref],
    );

    return (
      <SimpleSidebarContext.Provider value={contextValue}>
        <div
          style={
            {
              "--simple-sidebar-width": `${_width}px`,
              "--simple-sidebar-parent-width": `${_parentWidth}px`,
              ...style,
            } as React.CSSProperties
          }
          className={cn(
            "group/simple-sidebar-wrapper relative flex h-full w-full text-foreground",
            className,
          )}
          data-open={open}
          ref={combinedRef}
          {...props}
        >
          {children}
        </div>
      </SimpleSidebarContext.Provider>
    );
  },
);
SimpleSidebarProvider.displayName = "SimpleSidebarProvider";

const SimpleSidebarResizeHandle = React.forwardRef<
  HTMLButtonElement,
  React.ComponentProps<"button"> & {
    side?: "left" | "right";
  }
>(({ side = "right", className, ...props }, ref) => {
  const { setWidth, width, setIsResizing, isResizing } = useSimpleSidebar();
  const [dragStartX, setDragStartX] = React.useState(0);
  const [dragStartWidth, setDragStartWidth] = React.useState(0);

  const handleMouseDown = React.useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      setIsResizing(true);
      setDragStartX(e.clientX);
      setDragStartWidth(width);
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    },
    [width, setIsResizing],
  );

  const handleMouseMove = React.useCallback(
    (e: MouseEvent) => {
      if (!isResizing) return;

      const deltaX = e.clientX - dragStartX;
      const newWidth =
        side === "left" ? dragStartWidth + deltaX : dragStartWidth - deltaX;

      setWidth(newWidth);
    },
    [isResizing, dragStartX, dragStartWidth, setWidth, side],
  );

  const handleMouseUp = React.useCallback(() => {
    setIsResizing(false);
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
  }, [setIsResizing]);

  const handleKeyDown = React.useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        e.preventDefault();
        const increment = e.shiftKey ? 50 : 10;
        const delta = e.key === "ArrowLeft" ? -increment : increment;
        const newWidth = side === "left" ? width + delta : width - delta;
        setWidth(newWidth);
      }
    },
    [width, setWidth, side],
  );

  React.useEffect(() => {
    if (isResizing) {
      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);

      return () => {
        document.removeEventListener("mousemove", handleMouseMove);
        document.removeEventListener("mouseup", handleMouseUp);
      };
    }
  }, [isResizing, handleMouseMove, handleMouseUp]);

  React.useEffect(() => {
    return () => {
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, []);

  return (
    <button
      ref={ref}
      type="button"
      className={cn(
        "absolute top-0 bottom-0 z-50 w-1 cursor-col-resize transition-colors hover:bg-border focus:bg-border focus:outline-none border-0 bg-transparent p-0",
        side === "left" ? "right-0" : "left-0",
        isResizing && "bg-border",
        className,
      )}
      onMouseDown={handleMouseDown}
      onKeyDown={handleKeyDown}
      aria-label="Resize sidebar (use arrow keys or drag to resize)"
      {...props}
    >
      {/* Visual indicator */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="h-6 w-px bg-border/50" />
      </div>
    </button>
  );
});
SimpleSidebarResizeHandle.displayName = "SimpleSidebarResizeHandle";

const SimpleSidebar = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<"div"> & {
    side?: "left" | "right";
    resizable?: boolean;
  }
>(
  (
    { side = "right", resizable = true, className, children, ...props },
    ref,
  ) => {
    const { open, isResizing, fullscreen } = useSimpleSidebar();

    // Memoized animation values
    const spacerWidth = React.useMemo(() => {
      if (!open) return 0;
      return fullscreen ? "100%" : "var(--simple-sidebar-width)";
    }, [open, fullscreen]);

    const sidebarWidth = React.useMemo(() => {
      return fullscreen ? "100%" : "var(--simple-sidebar-width)";
    }, [fullscreen]);

    const xPosition = React.useMemo(() => {
      if (open) return "0%";
      return side === "left" ? "-100%" : "100%";
    }, [open, side]);

    const transitionDuration = React.useMemo(() => {
      return isResizing && !fullscreen ? 0 : 0.3;
    }, [isResizing, fullscreen]);

    return (
      <div
        ref={ref}
        className={cn(" flex h-full")}
        data-open={open}
        data-side={side}
        data-fullscreen={fullscreen}
      >
        {/* This is what handles the sidebar gap */}
        <motion.div
          className={cn("relative h-full bg-transparent")}
          animate={{
            width: spacerWidth,
          }}
          transition={{
            duration: transitionDuration,
            ease: "easeInOut",
          }}
        />
        <motion.div
          className={cn("absolute inset-y-0 z-50 flex h-full", className)}
          animate={{
            width: sidebarWidth,
            x: xPosition,
            opacity: open ? 1 : 0,
          }}
          transition={{
            duration: transitionDuration,
            ease: "easeInOut",
          }}
          style={{
            ...props.style,
            left: side === "left" ? 0 : "auto",
            right: side === "right" ? 0 : "auto",
            pointerEvents: open ? "auto" : "none",
          }}
        >
          <div
            data-simple-sidebar="sidebar"
            className="flex h-full w-full flex-col bg-background relative"
            style={{ visibility: open ? "visible" : "hidden" }}
          >
            {children}
            {resizable && open && !fullscreen && (
              <SimpleSidebarResizeHandle side={side} />
            )}
          </div>
        </motion.div>
      </div>
    );
  },
);
SimpleSidebar.displayName = "SimpleSidebar";

const SimpleSidebarTrigger = React.forwardRef<
  HTMLButtonElement,
  React.ComponentProps<"button">
>(({ className, onClick, children, ...props }, ref) => {
  const { toggleSidebar, open } = useSimpleSidebar();

  const handleClick = React.useCallback(
    (event: React.MouseEvent<HTMLButtonElement>) => {
      onClick?.(event);
      toggleSidebar();
    },
    [onClick, toggleSidebar],
  );

  return (
    <Button
      ref={ref}
      data-sidebar="trigger"
      data-testid="playground-btn-flow-io"
      variant="ghost"
      size="md"
      className={cn("!px-2 !font-normal !justify-start !gap-0", className)}
      onClick={handleClick}
      {...props}
    >
      {open ? (
        <PanelLeftOpen strokeWidth={1.5} />
      ) : (
        <PanelRightOpen strokeWidth={1.5} />
      )}
      {children && (
        <AnimatedConditional isOpen={!open}>
          <div className="pl-2">{children}</div>
        </AnimatedConditional>
      )}
    </Button>
  );
});
SimpleSidebarTrigger.displayName = "SimpleSidebarTrigger";

const SimpleSidebarHeader = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<"div">
>(({ className, ...props }, ref) => {
  return (
    <div
      ref={ref}
      data-simple-sidebar="header"
      className={cn("flex flex-col gap-2 p-2", className)}
      {...props}
    />
  );
});
SimpleSidebarHeader.displayName = "SimpleSidebarHeader";

const SimpleSidebarContent = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<"div">
>(({ className, ...props }, ref) => {
  return (
    <div
      ref={ref}
      data-simple-sidebar="content"
      className={cn(
        "flex min-h-0 flex-1 flex-col gap-2 overflow-auto",
        className,
      )}
      {...props}
    />
  );
});
SimpleSidebarContent.displayName = "SimpleSidebarContent";

export {
  SimpleSidebar,
  SimpleSidebarContent,
  SimpleSidebarHeader,
  SimpleSidebarProvider,
  SimpleSidebarResizeHandle,
  SimpleSidebarTrigger,
  useSimpleSidebar,
};
