import { cloneDeep } from "lodash";
import { useUpdateNodeInternals } from "reactflow";
import ForwardedIconComponent from "../../../../components/genericIconComponent";
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
}: outputComponentType) {
  const setNode = useFlowStore((state) => state.setNode);
  const updateNodeInternals = useUpdateNodeInternals();

  if (types.length < 2) {
    return <span className={cn(frozen ? " text-ice" : "")}>{selected}</span>;
  }

  return (
    <div className="nocopy nopan nodelete nodrag noundo flex gap-2 ">
      <span>{name}</span>
      <DropdownMenu>
        <DropdownMenuTrigger>
          <span
            className={cn(frozen ? " text-ice" : "", "flex items-center gap-1")}
          >
            {selected}
            <ForwardedIconComponent name="ChevronDown" className="h-4 w-4" />
          </span>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          {types.map((type) => (
            <DropdownMenuItem
              onSelect={() => {
                // TODO: UDPDATE SET NODE TO NEW NODE FORM
                setNode(nodeId, (node) => {
                  const newNode = cloneDeep(node);
                  (newNode.data as NodeDataType).node!.outputs![idx].selected =
                    type;
                  return newNode;
                });
                updateNodeInternals(nodeId);
              }}
            >
              {type}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
