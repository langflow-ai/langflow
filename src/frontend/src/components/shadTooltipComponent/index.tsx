import { ShadToolTipType } from "../../types/components";
import { cn } from "../../utils/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "../ui/tooltip";

export default function ShadTooltip({
  content,
  side,
  asChild = true,
  children,
  styleClasses,
  delayDuration = 500,
  open,
  setOpen,
}: ShadToolTipType): JSX.Element {
  return content ? (
    <Tooltip
      defaultOpen={!children}
      open={open}
      onOpenChange={setOpen}
      delayDuration={delayDuration}
    >
      <TooltipTrigger asChild={asChild}>{children}</TooltipTrigger>
      <TooltipContent
        className={cn("max-w-96", styleClasses)}
        side={side}
        avoidCollisions={false}
        sticky="always"
      >
        {content}
      </TooltipContent>
    </Tooltip>
  ) : (
    <>{children}</>
  );
}
