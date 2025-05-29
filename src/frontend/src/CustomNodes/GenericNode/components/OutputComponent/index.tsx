import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
        "text-xs font-medium",
        isToolMode && "text-secondary",
        frozen ? "text-ice" : "",
      )}
    >
      {name}
    </span>,
  );

  return (
    <div>
      {outputs.length > 1 ? (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              unstyled
              className="flex items-center gap-2"
              data-testid={`dropdown-output-${outputName?.toLowerCase()}`}
            >
              {name}
              <ForwardedIconComponent
                name="ChevronDown"
                className="h-4 w-4 text-muted-foreground"
              />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            {outputs.map((output) => (
              <DropdownMenuItem
                key={output.name}
                data-testid={`dropdown-item-output-${outputName?.toLowerCase()}-${output.display_name?.toLowerCase()}`}
                className="cursor-pointer px-3 py-2"
                onClick={() => {
                  handleSelectOutput && handleSelectOutput(output);
                }}
              >
                <span className="truncate text-[13px]">
                  {output.display_name ?? output.name}
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

  // ! DEACTIVATED UNTIL BETTER IMPLEMENTATION
  // return (
  //   <div className="noflow nopan nodelete nodrag  flex items-center gap-2">
  //     <DropdownMenu>
  //       <DropdownMenuTrigger asChild>
  //         <Button
  //           disabled={frozen}
  //           variant="primary"
  //           size="xs"
  //           className={cn(
  //             frozen ? "text-ice" : "",
  //             "items-center gap-1 pl-2 pr-1.5 align-middle text-xs font-normal",
  //           )}
  //         >
  //           <span className="pb-px">{selected}</span>
  //           <ForwardedIconComponent name="ChevronDown" className="h-3 w-3" />
  //         </Button>
  //       </DropdownMenuTrigger>
  //       <DropdownMenuContent>
  //         {types.map((type) => (
  //           <DropdownMenuItem
  //             onSelect={() => {
  //               // TODO: UDPDATE SET NODE TO NEW NODE FORM
  //               setNode(nodeId, (node) => {
  //                 const newNode = cloneDeep(node);
  //                 (newNode.data as NodeDataType).node!.outputs![idx].selected =
  //                   type;
  //                 return newNode;
  //               });
  //               updateNodeInternals(nodeId);
  //             }}
  //           >
  //             {type}
  //           </DropdownMenuItem>
  //         ))}
  //       </DropdownMenuContent>
  //     </DropdownMenu>
  //     {proxy ? (
  //       <ShadTooltip content={<span>{proxy.nodeDisplayName}</span>}>
  //         <span>{name}</span>
  //       </ShadTooltip>
  //     ) : (
  //       <span>{name}</span>
  //     )}
  //   </div>
  // );
}
