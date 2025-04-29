import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useState } from "react";
import ShadTooltip from "../../../../components/common/shadTooltipComponent";
import { outputComponentType } from "../../../../types/components";
import { cn } from "../../../../utils/utils";

export default function OutputComponent({
  selected,
  types,
  frozen = false,
  nodeId,
  idx,
  name,
  proxy,
  isToolMode = false,
}: outputComponentType) {
  const [selectedName, setSelectedName] = useState("Button");

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
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          unstyled
          className="item-center group flex text-[13px] font-medium"
        >
          {selectedName}
          <ForwardedIconComponent
            name="ChevronDown"
            className="icon-size h-4.5 w-4.5 mx-1 font-medium text-muted-foreground group-hover:text-foreground"
            strokeWidth={2}
          />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent forceMount>
        <DropdownMenuItem
          className="deploy-dropdown-item group"
          onClick={() => {
            setSelectedName("Button");
          }}
        >
          <div className="group-hover:bg-accent">
            <span>Auto-detect</span>
          </div>
        </DropdownMenuItem>
        <DropdownMenuItem
          className="deploy-dropdown-item group"
          onClick={() => {
            setSelectedName(name);
          }}
        >
          <div className="group-hover:bg-accent">
            <span>{name}</span>
          </div>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>,
    // <span
    //   className={cn(
    //     "text-xs font-medium",
    //     isToolMode && "text-secondary",
    //     frozen ? "text-ice" : "",
    //   )}
    // >
    //   {name}
    // </span>,
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
