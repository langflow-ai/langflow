import React from "react";
import { ShadToolTipType } from "../../types/components";
import { cn } from "../../utils/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "../ui/tooltip";

const ShadTooltip: React.FC<ShadToolTipType> = ({
  content,
  side,
  asChild = true,
  children,
  styleClasses,
  delayDuration = 500,
  open,
  align,
  setOpen,
}) => {
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
        className={cn(
          "z-50 max-w-96 bg-tooltip text-[12px] text-tooltip-foreground",
          styleClasses,
        )}
        side={side}
        avoidCollisions={false}
        align={align}
        sticky="always"
      >
        {content}
      </TooltipContent>
    </Tooltip>
  );
};

export default ShadTooltip;
