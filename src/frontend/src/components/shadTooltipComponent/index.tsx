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
  setOpen,
  contrastTooltip = false,
}) => {
  if (!content) {
    return <>{children}</>;
  }

  const tooltipContentClass = cn(
    "max-w-96  self-center content-center",
    styleClasses,
    contrastTooltip
      ? "bg-foreground text-background dark:bg-background dark:text-foreground text-[12px]"
      : "",
  );

  return (
    <Tooltip
      defaultOpen={!children}
      open={open}
      onOpenChange={setOpen}
      delayDuration={delayDuration}
    >
      <TooltipTrigger asChild={asChild}>{children}</TooltipTrigger>
      <TooltipContent
        className={tooltipContentClass}
        side={side}
        avoidCollisions={false}
        sticky="always"
      >
        {content}
      </TooltipContent>
    </Tooltip>
  );
};

export default ShadTooltip;
