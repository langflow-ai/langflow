import { cloneDeep } from "lodash";
import { useUpdateNodeInternals } from "reactflow";
import ForwardedIconComponent from "../../../../components/genericIconComponent";
import ShadTooltip from "../../../../components/shadTooltipComponent";
import { Button } from "../../../../components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../../../../components/ui/dropdown-menu";
import useFlowStore from "../../../../stores/flowStore";
import { outputComponentType } from "../../../../types/components";
import { NodeDataType } from "../../../../types/flow";
import { cn } from "../../../../utils/utils";

export default function OutputComponent({
  selected,
  types,
  frozen = false,
  nodeId,
  idx,
  name,
  proxy,
}: outputComponentType) {
  const setNode = useFlowStore((state) => state.setNode);
  const updateNodeInternals = useUpdateNodeInternals();

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

  return displayProxy(
    <span className={cn(frozen ? "text-ice" : "")}>{name}</span>,
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
