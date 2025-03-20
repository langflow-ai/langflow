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
  variant?: "large" | "small";
}

const MorphingMenu = React.forwardRef<HTMLDivElement, MorphingMenuProps>(
  (
    { trigger, items, className, buttonClassName, itemsClassName, variant },
    ref,
  ) => {
    const [isOpen, setIsOpen] = React.useState(false);

    // Calculate menu height: header (40px) + (items * 36px) + padding (16px)
    const menuHeight = (variant == "large" ? 40 : 32) + items.length * 32 + 8;

    return (
      <div
        ref={ref}
        className={cn(
          "relative flex w-fit select-none flex-col items-center justify-center whitespace-nowrap transition-all",
          variant === "large" ? "h-10" : "h-8",
          isOpen ? "w-40" : variant === "large" ? "w-36" : "w-[134px]",
          className,
        )}
      >
        <div
          style={{
            height: isOpen
              ? `${menuHeight}px`
              : variant === "large"
                ? "40px"
                : "32px",
          }}
          className={cn(
            "absolute right-0 top-0 z-50 flex w-full flex-col items-start overflow-hidden bg-primary text-sm font-semibold text-primary-foreground transition-all duration-200",
            !isOpen && "hover:bg-primary-hover",
            variant === "large" ? "rounded-md" : "rounded-lg",
            buttonClassName,
          )}
        >
          <div
            className={cn(
              "flex w-full shrink-0 cursor-pointer items-center justify-between gap-2 pl-3 pr-3 transition-all",
              variant === "large" ? "h-10" : "h-8 text-[13px] font-medium",
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
