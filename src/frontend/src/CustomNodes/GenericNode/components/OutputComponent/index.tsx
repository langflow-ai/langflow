import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useUpdateNodeInternals } from "@xyflow/react";
import { cloneDeep } from "lodash";
import { useMemo, useState } from "react";
import ShadTooltip from "../../../../components/common/shadTooltipComponent";
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
  isToolMode = false,
  outputs,
}: outputComponentType) {
  const singleOutput = useMemo(() => {
    return outputs?.length > 1 ? false : true;
  }, [outputs]);

  const [selectedName, setSelectedName] = useState(outputs?.[0].display_name);
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

  const handleOutputSelection = (output) => {
    // Update the display name in the dropdown
    setSelectedName(output.display_name);

    // Update the node data to reflect the selected output type
    setNode(nodeId, (node) => {
      const newNode = cloneDeep(node);
      if (newNode.data && newNode.data.node && newNode.data.node.outputs) {
        (newNode.data as NodeDataType).node!.outputs![idx].selected =
          output.types[0];
      }
      return newNode;
    });

    // Trigger a refresh of the node to update handle colors
    updateNodeInternals(nodeId);
  };

  return displayProxy(
    <DropdownMenu>
      <DropdownMenuTrigger asChild disabled={singleOutput}>
        <Button
          unstyled
          className={cn(
            "item-center group flex text-[13px] font-medium",
            singleOutput && "mr-2",
          )}
          style={
            selectedName === "Auto-detect"
              ? {
                  color: "transparent",
                  backgroundClip: "text",
                  backgroundImage:
                    "linear-gradient(90deg, #F472B6 0%, #C084FC 50%)",
                }
              : {}
          }
        >
          {selectedName}
          {!singleOutput && (
            <ForwardedIconComponent
              name="ChevronDown"
              className="icon-size h-4.5 w-4.5 mx-1 font-medium text-muted-foreground group-hover:text-foreground"
              strokeWidth={2}
            />
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent forceMount className="min-w-[200px]">
        {/* TODO: When we have a way to auto-detect the output type, we can add this back */}
        {/* <DropdownMenuItem
          onClick={() => {
            setSelectedName("Auto-detect");
          }}
        >
          <div className="w-full p-1 text-[13px] font-medium hover:bg-muted">
            <span
              style={{
                color: "transparent",
                backgroundClip: "text",
                backgroundImage:
                  "linear-gradient(90deg, #F472B6 0%, #C084FC 50%)",
              }}
            >
              Auto-detect
            </span>
          </div>
        </DropdownMenuItem> */}
        {outputs &&
          outputs.map((item) => (
            <DropdownMenuItem
              key={item.name}
              onClick={() => {
                handleOutputSelection(item);
              }}
            >
              <div className="w-full p-1 text-[13px] font-medium hover:bg-muted">
                <span>{item.display_name}</span>
              </div>
            </DropdownMenuItem>
          ))}
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
