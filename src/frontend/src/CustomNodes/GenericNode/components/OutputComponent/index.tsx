import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import useFlowStore from "@/stores/flowStore";
import ShadTooltip from "../../../../components/common/shadTooltipComponent";
import { outputComponentType } from "../../../../types/components";
import { cn } from "../../../../utils/utils";

export default function OutputComponent({
  selected,
  types,
  frozen = false,
  nodeId,
  outputs,
  idx,
  name,
  proxy,
  isToolMode = false,
  handleSelectOutput,
  outputName,
}: outputComponentType) {
  const nodeType = useFlowStore(
    (state) => state.nodes.find((node) => node.id === nodeId)?.data?.type,
  );

  const displayProxy = (children) => {
    if (proxy) {
      return (
        <ShadTooltip content={<span>{proxy.nodeDisplayName}</span>}>
          {children}
        </ShadTooltip>
      );
    } else {
      return children;
    }
  };

  const singleOutput = displayProxy(
    <span
      className={cn(
        "px-2 py-1 text-[13px] font-medium",
        isToolMode && "text-secondary",
        frozen ? "text-ice" : "",
      )}
    >
      {name}
    </span>,
  );

  const hasLoopOutput = outputs?.some?.((output) => output.allows_loop);
  const hasGroupOutputs = outputs?.some?.((output) => output.group_outputs);
  const isConditionalRouter = nodeType === "ConditionalRouter";
  const hasOutputs = outputs.length > 1;

  const shouldShowDropdown =
    hasOutputs && !hasLoopOutput && !hasGroupOutputs && !isConditionalRouter;

  return (
    <div>
      {shouldShowDropdown ? (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              unstyled
              className="group flex items-center gap-2"
              data-testid={`dropdown-output-${outputName?.toLowerCase()}`}
            >
              <div className="flex items-center gap-1 truncate rounded-md px-2 py-1 text-[13px] font-medium group-hover:bg-primary/10">
                {name}
                <ForwardedIconComponent
                  name="ChevronDown"
                  className="h-4 w-4 text-muted-foreground"
                />
              </div>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="min-w-[200px] max-w-[250px]">
            {outputs.map((output) => (
              <DropdownMenuItem
                key={output.name}
                data-testid={`dropdown-item-output-${outputName?.toLowerCase()}-${output.display_name?.toLowerCase()}`}
                className="cursor-pointer justify-between px-3 py-2"
                onClick={() => {
                  handleSelectOutput && handleSelectOutput(output);
                }}
              >
                <span className="truncate text-[13px]">
                  {output.display_name ?? output.name}
                </span>
                <span className="ml-4 text-[13px] text-muted-foreground">
                  {output.types.join(", ")}
                </span>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      ) : (
        singleOutput
      )}
    </div>
  );
}
