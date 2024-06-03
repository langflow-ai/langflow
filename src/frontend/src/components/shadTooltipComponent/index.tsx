import { ShadToolTipType } from "../../types/components";
import { cn } from "../../utils/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipContentWithoutPortal,
  TooltipTrigger,
} from "../ui/tooltip";

export default function ShadTooltip({
  content,
  side,
  asChild = true,
  children,
  styleClasses,
  portal = true,
  delayDuration = 500,
}: ShadToolTipType): JSX.Element {
  const TooltipContentComponent = portal
    ? TooltipContent
    : TooltipContentWithoutPortal;
  return (
    <Tooltip delayDuration={delayDuration}>
      <TooltipTrigger asChild={asChild}>{children}</TooltipTrigger>
      <TooltipContentComponent
        className={cn(styleClasses, "max-w-96")}
        side={side}
        avoidCollisions={false}
        sticky="always"
      >
        {content}
      </TooltipContentComponent>
    </Tooltip>
  );
}
