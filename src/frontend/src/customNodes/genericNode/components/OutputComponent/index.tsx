import ForwardedIconComponent from "../../../../components/genericIconComponent";
import { outputComponentType } from "../../../../types/components";
import { cn } from "../../../../utils/utils";
import useFlowStore from "../../../../stores/flowStore";
import { NodeDataType } from "../../../../types/flow";
import { cloneDeep } from "lodash";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../../../../components/ui/dropdown-menu";

export default function OutputComponent({
  selected,
  types,
  frozen = false,
  nodeId,
  idx,
}: outputComponentType) {
  const setNode = useFlowStore((state) => state.setNode);

  if (types.length < 2) {
    return <span className={cn(frozen ? " text-ice" : "")}>{selected}</span>;
  }

  return (
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
            }}
          >
            {type}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
