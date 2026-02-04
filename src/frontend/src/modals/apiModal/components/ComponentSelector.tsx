import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useTweaksStore } from "@/stores/tweaksStore";
import type { AllNodeType } from "@/types/flow";

interface ComponentSelectorProps {
  selectedComponentId: string | null;
  onComponentSelect: (componentId: string | null) => void;
}

export function ComponentSelector({
  selectedComponentId,
  onComponentSelect,
}: ComponentSelectorProps) {
  const nodes = useTweaksStore((state) => state.nodes);

  // Filter out output components (ChatOutput, APIResponse, etc.)
  const inputNodes =
    nodes?.filter((node: AllNodeType) => {
      const nodeType = node.data?.node?.display_name || node.data?.type;
      return (
        nodeType &&
        !nodeType.endsWith("Output") &&
        !nodeType.includes("Response")
      );
    }) || [];

  const selectedNode = selectedComponentId
    ? nodes?.find((node: AllNodeType) => node.data.id === selectedComponentId)
    : null;

  return (
    <div className="flex flex-col gap-3 pr-2">
      <Select
        value={selectedComponentId || ""}
        onValueChange={(value) => onComponentSelect(value || null)}
      >
        <SelectTrigger className="w-full h-10 border-border bg-card hover:bg-accent/50 focus:ring-0 focus:ring-offset-0">
          <SelectValue placeholder="Select a component..." />
        </SelectTrigger>
        <SelectContent>
          {inputNodes.map((node: AllNodeType) => {
            const componentIcon = node.data?.node?.icon || node.data?.type;
            return (
              <SelectItem
                key={node.data?.id || node.id}
                value={node.data?.id || node.id}
              >
                <div className="flex items-center gap-2">
                  <IconComponent name={componentIcon} className="h-4 w-4" />
                  <span className="font-medium">
                    {node.data?.id || node.id}
                  </span>
                </div>
              </SelectItem>
            );
          })}
          {inputNodes.length === 0 && (
            <SelectItem value="" disabled>
              No input components available
            </SelectItem>
          )}
        </SelectContent>
      </Select>
    </div>
  );
}
