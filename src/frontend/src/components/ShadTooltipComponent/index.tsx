import { ShadTooltipProps } from "../../types/components";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../ui/tooltip";

const ShadTooltip = ({
  delayDuration = 500,
  side,
  content,
  children,
}: ShadTooltipProps) => {
  return (
    <TooltipProvider>
      <Tooltip delayDuration={delayDuration}>
        <TooltipTrigger asChild>{children}</TooltipTrigger>

        <TooltipContent side={side} avoidCollisions={false} sticky="always">
          {content}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

export default ShadTooltip;
