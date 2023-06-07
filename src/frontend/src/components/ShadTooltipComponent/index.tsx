import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../ui/tooltip";

const ShadTooltip = (props) => {
  return (
    <TooltipProvider>
      <Tooltip delayDuration={props.delayDuration}>
        <TooltipTrigger asChild>{props.children}</TooltipTrigger>
        <TooltipContent
          side={props.side}
          avoidCollisions={false}
          sticky="always"
        >
          {props.content}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

export default ShadTooltip;
