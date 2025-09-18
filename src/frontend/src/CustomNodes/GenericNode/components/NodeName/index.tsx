import { useEffect, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Input } from "@/components/ui/input";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { getEffectiveAliasFromAnyNode } from "@/types/flow";
import { updateAliasesForDisplayNameChange } from "@/utils/aliasUtils";
import { cn } from "@/utils/utils";

export default function NodeName({
  display_name,
  selected,
  nodeId,
  showNode,
  beta,
  editNameDescription,
  toggleEditNameDescription,
  setHasChangedNodeDescription,
}: {
  display_name?: string;
  selected?: boolean;
  nodeId: string;
  showNode: boolean;
  beta: boolean;
  editNameDescription: boolean;
  toggleEditNameDescription: () => void;
  setHasChangedNodeDescription: (hasChanged: boolean) => void;
}) {
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  const setNode = useFlowStore((state) => state.setNode);
  const node = useFlowStore((state) => state.getNode(nodeId));

  // Get alias for badge display
  const componentAlias = node ? getEffectiveAliasFromAnyNode(node) : null;
  const aliasNumber = componentAlias?.match(/#(\d+)$/)?.[1];

  const [nodeName, setNodeName] = useState<string>(display_name ?? "");

  useEffect(() => {
    if (selected && editNameDescription) {
      takeSnapshot();
    }
  }, [editNameDescription]);

  useEffect(() => {
    setNodeName(display_name ?? "");
  }, [display_name]);

  const handleBlur = () => {
    if (nodeName?.trim() !== "") {
      const oldDisplayName = display_name;
      const newDisplayName = nodeName;

      setNodeName(nodeName);
      setNode(nodeId, (old) => ({
        ...old,
        data: {
          ...old.data,
          node: {
            ...old.data.node,
            display_name: nodeName,
          },
        },
      }));

      // Update aliases when display name changes
      if (oldDisplayName && newDisplayName !== oldDisplayName) {
        const allNodes = useFlowStore.getState().nodes;
        const updatedNodes = updateAliasesForDisplayNameChange(
          nodeId,
          oldDisplayName,
          newDisplayName,
          allNodes,
        );
        useFlowStore.getState().setNodes(updatedNodes);
      }
    } else {
      setNodeName(display_name ?? "");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleBlur();
      toggleEditNameDescription();
    }
    if (e.key === "Escape") {
      setNodeName(display_name ?? "");
      toggleEditNameDescription();
    }
  };

  const onChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setNodeName(e.target.value);
    setHasChangedNodeDescription(true);
  };

  return editNameDescription ? (
    <div className="w-full">
      <Input
        onBlur={handleBlur}
        value={nodeName}
        autoFocus
        onChange={onChange}
        data-testid={`input-title-${display_name}`}
        onKeyDown={handleKeyDown}
        className="px-2 py-0"
      />
    </div>
  ) : (
    <div className="group my-px flex flex-1 items-center gap-2 overflow-hidden">
      <div
        data-testid={"title-" + display_name}
        className={cn(
          "nodoubleclick truncate font-medium text-primary",
          showNode ? "cursor-text" : "cursor-default",
        )}
      >
        <div className="flex cursor-grab items-center gap-2">
          <span className={cn("cursor-grab truncate text-sm")}>
            {display_name}
          </span>
          {aliasNumber && (
            <ShadTooltip content={`Alias: ${componentAlias}`}>
              <div className="flex h-5 w-auto min-w-[18px] items-center justify-center rounded border border-border bg-background px-1.5 text-xs font-semibold text-foreground">
                #{aliasNumber}
              </div>
            </ShadTooltip>
          )}
        </div>
      </div>
      {beta && (
        <div className="shrink-0">
          <ShadTooltip content="Beta component">
            <div className="flex h-4 w-4 items-center justify-center rounded-sm border border-accent-purple-foreground p-0.5">
              <ForwardedIconComponent
                name="FlaskConical"
                className="text-accent-purple-foreground"
              />
            </div>
          </ShadTooltip>
        </div>
      )}
    </div>
  );
}
