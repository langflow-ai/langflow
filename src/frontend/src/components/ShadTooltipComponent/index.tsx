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
  style,
}: ShadTooltipProps) => {
  return (
    <TooltipProvider>
      <Tooltip delayDuration={delayDuration}>
        <TooltipTrigger asChild>{children}</TooltipTrigger>

        <TooltipContent
          className={style}
          side={side}
          avoidCollisions={false}
          sticky="always"
        >
          {content}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

export default ShadTooltip;
