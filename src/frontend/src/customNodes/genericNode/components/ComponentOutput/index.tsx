import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@radix-ui/react-dropdown-menu";
import ForwardedIconComponent from "../../../../components/genericIconComponent";
import { outputComponentType } from "../../../../types/components";
import { cn } from "../../../../utils/utils";
import useFlowStore from "../../../../stores/flowStore";

export default function ComponentOutput({
  selected,
  types,
  frozen = false,
  nodeId,
}: outputComponentType) {
  const setNode = useFlowStore((state) => state.setNode);
  let displayTitle = selected ?? types[0];

  if (types.length < 2) {
    return (
      <span className={cn(frozen ? " text-ice" : "")}>{displayTitle}</span>
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger>
        <span
          className={cn(frozen ? " text-ice" : "", "flex items-center gap-1")}
        >
          {displayTitle}
          <ForwardedIconComponent name="ChevronDown" className="h-4 w-4" />
        </span>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        {types.map((type) => (
          <DropdownMenuItem
            onSelect={() => {
              // TODO: UDPDATE SET NODE TO NEW NODE FORM
              setNode(nodeId, (node) => ({
                ...node,
                data: { ...node.data, selected: type },
              }));
            }}
          >
            {type}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
