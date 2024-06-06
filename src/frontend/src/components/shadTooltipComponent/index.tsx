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
}: ShadToolTipType): JSX.Element {
  return (
    <Tooltip defaultOpen={!children} delayDuration={delayDuration}>
      <TooltipTrigger asChild={asChild}>{children}</TooltipTrigger>
      <TooltipContent
        className={cn(styleClasses, "max-w-96")}
        side={side}
        avoidCollisions={false}
        sticky="always"
      >
        {content}
      </TooltipContent>
    </Tooltip>
  );
}
