"use client";

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
};

const SimpleSidebarContext = React.createContext<SimpleSidebarContext | null>(
  null
);

function useSimpleSidebar() {
  const context = React.useContext(SimpleSidebarContext);
  if (!context) {
    throw new Error(
      "useSimpleSidebar must be used within a SimpleSidebarProvider."
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
      ...props
    },
    ref
  ) => {
    // This is the internal state of the sidebar.
    // We use openProp and setOpenProp for control from outside the component.
    const [_open, _setOpen] = React.useState(defaultOpen);
    const [_width, _setWidth] = React.useState(
      typeof width === "string" ? parseInt(width.replace("px", "")) : width
    );
    const [_isResizing, _setIsResizing] = React.useState(false);

    const open = openProp ?? _open;
    const setOpen = React.useCallback(
      (value: boolean | ((value: boolean) => boolean)) => {
        if (setOpenProp) {
          return setOpenProp?.(
            typeof value === "function" ? value(open) : value
          );
        }

        _setOpen(value);
      },
      [setOpenProp, open]
    );

    const setWidth = React.useCallback((newWidth: number) => {
      const constrainedWidth = Math.min(
        Math.max(newWidth, MIN_SIDEBAR_WIDTH),
        MAX_SIDEBAR_WIDTH
      );
      _setWidth(constrainedWidth);
    }, []);

    // Helper to toggle the sidebar.
    const toggleSidebar = React.useCallback(() => {
      return setOpen((prev) => !prev);
    }, [setOpen]);

    const contextValue = React.useMemo<SimpleSidebarContext>(
      () => ({
        open,
        setOpen,
        toggleSidebar,
        width: _width,
        setWidth,
        isResizing: _isResizing,
        setIsResizing: _setIsResizing,
      }),
      [open, setOpen, toggleSidebar, _width, setWidth, _isResizing]
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
      }
    );

    return (
      <SimpleSidebarContext.Provider value={contextValue}>
        <div
          style={
            {
              "--simple-sidebar-width": `${_width}px`,
              ...style,
            } as React.CSSProperties
          }
          className={cn(
            "group/simple-sidebar-wrapper flex h-full w-full text-foreground",
            className
          )}
          data-open={open}
          ref={ref}
          {...props}
        >
          {children}
        </div>
      </SimpleSidebarContext.Provider>
    );
  }
);
SimpleSidebarProvider.displayName = "SimpleSidebarProvider";

const SimpleSidebarResizeHandle = React.forwardRef<
  HTMLButtonElement,
  React.ComponentProps<"button"> & {
    side?: "left" | "right";
  }
>(({ side = "right", className, ...props }, ref) => {
  const {
    setWidth,
    width,
    setIsResizing: setGlobalIsResizing,
  } = useSimpleSidebar();
  const [isResizing, setIsResizing] = React.useState(false);
  const [dragStartX, setDragStartX] = React.useState(0);
  const [dragStartWidth, setDragStartWidth] = React.useState(0);

  const handleMouseDown = React.useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      setIsResizing(true);
      setGlobalIsResizing(true);
      setDragStartX(e.clientX);
      setDragStartWidth(width);
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    },
    [width, setGlobalIsResizing]
  );

  const handleMouseMove = React.useCallback(
    (e: MouseEvent) => {
      if (!isResizing) return;

      const deltaX = e.clientX - dragStartX;
      const newWidth =
        side === "left" ? dragStartWidth + deltaX : dragStartWidth - deltaX;

      setWidth(newWidth);
    },
    [isResizing, dragStartX, dragStartWidth, setWidth, side]
  );

  const handleMouseUp = React.useCallback(() => {
    setIsResizing(false);
    setGlobalIsResizing(false);
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
  }, [setGlobalIsResizing]);

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
    [width, setWidth, side]
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

  return (
    <button
      ref={ref}
      type="button"
      className={cn(
        "absolute top-0 bottom-0 z-50 w-1 cursor-col-resize transition-colors hover:bg-border focus:bg-border focus:outline-none border-0 bg-transparent p-0",
        side === "left" ? "right-0" : "left-0",
        isResizing && "bg-border",
        className
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
    ref
  ) => {
    const { open, isResizing } = useSimpleSidebar();

    return (
      <div
        ref={ref}
        className="relative block h-full flex-col"
        data-open={open}
        data-side={side}
      >
        {/* This is what handles the sidebar gap */}
        <div
          className={cn(
            "relative h-full w-[--simple-sidebar-width] bg-transparent",
            !isResizing && "transition-[width] duration-300 ease-in-out",
            !open && "w-0"
          )}
        />
        <div
          className={cn(
            "absolute inset-y-0 z-50 flex h-full w-[--simple-sidebar-width]",
            !isResizing &&
              "transition-[left,right,width] duration-300 ease-in-out",
            side === "left"
              ? cn(
                  "left-0",
                  !open && "left-[calc(var(--simple-sidebar-width)*-1)]"
                )
              : cn(
                  "right-0",
                  !open && "right-[calc(var(--simple-sidebar-width)*-1)]"
                ),
            className
          )}
          {...props}
        >
          <div
            data-simple-sidebar="sidebar"
            className="flex h-full w-full flex-col bg-background relative"
          >
            {children}
            {resizable && open && <SimpleSidebarResizeHandle side={side} />}
          </div>
        </div>
      </div>
    );
  }
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
    [onClick, toggleSidebar]
  );

  return (
    <Button
      ref={ref}
      data-sidebar="trigger"
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
        className
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
