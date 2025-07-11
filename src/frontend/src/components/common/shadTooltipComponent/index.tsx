import type React from "react";
import { forwardRef, memo, useMemo } from "react";
import type { ShadToolTipType } from "../../../types/components";
import { cn } from "../../../utils/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "../../ui/tooltip";

// Extract static styles
const BASE_TOOLTIP_CLASSES =
  "z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground";

// Memoize the tooltip content component
const MemoizedTooltipContent = memo(
  forwardRef<
    HTMLDivElement,
    {
      className?: string;
      side?: ShadToolTipType["side"];
      avoidCollisions?: boolean;
      align?: ShadToolTipType["align"];
      children: React.ReactNode;
    }
  >((props, ref) => (
    <TooltipContent
      ref={ref}
      className={props.className}
      side={props.side}
      avoidCollisions={props.avoidCollisions}
      align={props.align}
      sticky="always"
    >
      {props.children}
    </TooltipContent>
  )),
);

MemoizedTooltipContent.displayName = "MemoizedTooltipContent";

// Memoize the main tooltip component
const ShadTooltip = memo(
  forwardRef<HTMLDivElement, ShadToolTipType>(
    (
      {
        content,
        side,
        asChild = true,
        children,
        styleClasses,
        delayDuration = 500,
        open,
        align,
        setOpen,
        avoidCollisions = false,
      },
      ref,
    ) => {
      // Early return if no content
      if (!content) {
        return children;
      }

      // Memoize className concatenation
      const tooltipClassName = useMemo(
        () => cn(BASE_TOOLTIP_CLASSES, styleClasses),
        [styleClasses],
      );

      // Memoize tooltip props
      const tooltipProps = useMemo(
        () => ({
          defaultOpen: !children,
          open,
          onOpenChange: setOpen,
          delayDuration,
        }),
        [children, open, setOpen, delayDuration],
      );

      return (
        <Tooltip {...tooltipProps}>
          <TooltipTrigger asChild={asChild}>{children}</TooltipTrigger>
          <MemoizedTooltipContent
            ref={ref}
            className={tooltipClassName}
            side={side}
            avoidCollisions={avoidCollisions}
            align={align}
          >
            {content}
          </MemoizedTooltipContent>
        </Tooltip>
      );
    },
  ),
);

// Add display name for dev tools
ShadTooltip.displayName = "ShadTooltip";
export default ShadTooltip;
