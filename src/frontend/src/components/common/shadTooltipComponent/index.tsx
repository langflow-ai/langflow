import React, { forwardRef } from "react";
import { ShadToolTipType } from "../../../types/components";
import { cn } from "../../../utils/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "../../ui/tooltip";

const ShadTooltip = forwardRef<HTMLDivElement, ShadToolTipType>(
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
    if (!content) {
      return <>{children}</>;
    }

    return (
      <Tooltip
        defaultOpen={!children}
        open={open}
        onOpenChange={setOpen}
        delayDuration={delayDuration}
      >
        <TooltipTrigger asChild={asChild}>{children}</TooltipTrigger>
        <TooltipContent
          ref={ref}
          className={cn(
            "z-[99] max-w-96 bg-tooltip text-[12px] text-tooltip-foreground",
            styleClasses,
          )}
          side={side}
          avoidCollisions={avoidCollisions}
          align={align}
          sticky="always"
        >
          {content}
        </TooltipContent>
      </Tooltip>
    );
  },
);

ShadTooltip.displayName = "ShadTooltip";

export default ShadTooltip;
