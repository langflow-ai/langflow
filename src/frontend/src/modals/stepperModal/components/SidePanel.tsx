import type { ReactNode } from "react";
import { cn } from "@/utils/utils";
import { SIDE_PANEL_WIDTH } from "../constants";

interface SidePanelProps {
  children: ReactNode;
  open: boolean;
}

export function SidePanel({ children, open }: SidePanelProps) {
  return (
    <div
      className={cn(
        "absolute left-full top-[-1px] bottom-[-1px] flex transition-opacity duration-150",
        open ? "opacity-100" : "opacity-0 pointer-events-none",
      )}
    >
      {/* Vertical separator line */}
      <div className="w-[1px] shrink-0 bg-border" />
      {/* Sliding panel content */}
      <div className="overflow-hidden">
        <div
          className={cn(
            "h-full transition-transform duration-300 ease-out",
            open ? "translate-x-0" : "-translate-x-full",
          )}
        >
          <div
            className={cn(
              "flex h-full flex-col rounded-r-xl border-y border-r bg-background shadow-lg",
              SIDE_PANEL_WIDTH,
            )}
          >
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
