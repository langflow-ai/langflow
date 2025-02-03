"use client";

import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";
import * as React from "react";

interface MorphingMenuProps {
  trigger: React.ReactNode;
  items: {
    icon?: string;
    label: string;
    onClick?: () => void;
  }[];
  className?: string;
  buttonClassName?: string;
  itemsClassName?: string;
}

const MorphingMenu = React.forwardRef<HTMLDivElement, MorphingMenuProps>(
  ({ trigger, items, className, buttonClassName, itemsClassName }, ref) => {
    const [isOpen, setIsOpen] = React.useState(false);

    // Calculate menu height: header (40px) + (items * 36px) + padding (16px)
    const menuHeight = 40 + items.length * 32 + 8;

    return (
      <div
        ref={ref}
        className={cn(
          "relative flex h-10 w-fit select-none flex-col items-center justify-center whitespace-nowrap transition-all",
          isOpen ? "w-40" : "w-36",
          className,
        )}
      >
        <div
          style={{ height: isOpen ? `${menuHeight}px` : "40px" }}
          className={cn(
            "absolute right-0 top-0 z-50 flex w-full flex-col items-start overflow-hidden rounded-md bg-primary text-sm font-semibold text-primary-foreground transition-all duration-200",
            !isOpen && "hover:bg-primary-hover",
            buttonClassName,
          )}
        >
          <div
            className={cn(
              "flex h-10 w-full shrink-0 cursor-pointer items-center justify-between gap-2 px-3 transition-all",
            )}
            onClick={() => setIsOpen(!isOpen)}
          >
            {trigger}
            <div className="flex h-4 w-4 items-center justify-center">
              <ForwardedIconComponent
                name="ChevronDown"
                className={cn(
                  "absolute h-4 w-4 transition-all",
                  isOpen && "opacity-0",
                )}
              />
              <ForwardedIconComponent
                name="X"
                className={cn(
                  "absolute h-4 w-4 opacity-0 transition-all",
                  isOpen && "opacity-100",
                )}
              />
            </div>
          </div>
          <div
            className={cn(
              "flex w-full flex-col gap-0 px-2 font-medium",
              itemsClassName,
            )}
          >
            {items.map((item, index) => (
              <div
                key={index}
                className="relative flex h-8 cursor-pointer select-none items-center gap-2 rounded-sm px-2 text-sm outline-none transition-colors hover:bg-primary-hover"
                onClick={() => {
                  item.onClick?.();
                  setIsOpen(false);
                }}
              >
                {item.icon && (
                  <ForwardedIconComponent
                    name={item.icon}
                    className="h-4 w-4"
                  />
                )}
                {item.label}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  },
);

MorphingMenu.displayName = "MorphingMenu";

export { MorphingMenu };
export type { MorphingMenuProps };
