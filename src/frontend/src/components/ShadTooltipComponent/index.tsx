import { ShadTooltipType } from "../../types/components";
import { NodeType } from "../../types/flow";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../ui/tooltip";

export default function ShadTooltip({ children, delayDuration = 1000, content, side, open }: ShadTooltipType) {
  return (
    <TooltipProvider>
      <Tooltip delayDuration={delayDuration}>
        <TooltipTrigger asChild>{children}</TooltipTrigger>

        <TooltipContent
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
