import { ShadToolTipType } from "../../types/components";
import { cn } from "../../utils/utils";
import Scroller from "../ui/scroller";
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
    <Tooltip delayDuration={delayDuration}>
      <TooltipTrigger asChild={asChild}>{children}</TooltipTrigger>

      <TooltipContent
        className={cn(styleClasses, "max-w-96")}
        side={side}
        avoidCollisions={false}
        sticky="always"
        asChild
      >
        <Scroller>{content}</Scroller>
      </TooltipContent>
    </Tooltip>
  );
}
