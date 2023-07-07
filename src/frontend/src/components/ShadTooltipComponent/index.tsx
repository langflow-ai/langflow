import { RadialProgressType, ShadToolTipType } from "../../types/components";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../ui/tooltip";

export default function ShadTooltip({
  content,
  side,
  asChild = true,
  children,
  delayDuration,
  style
}: ShadToolTipType) {
  return (
    <TooltipProvider>
      <Tooltip delayDuration={delayDuration}>
        <TooltipTrigger asChild={asChild}>{children}</TooltipTrigger>

        <TooltipContent className={style} side={side} avoidCollisions={false} sticky="always">
          {content}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
