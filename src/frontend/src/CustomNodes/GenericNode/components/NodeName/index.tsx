import { Input } from "@/components/ui/input";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useFlowStore from "@/stores/flowStore";
import { VertexBuildTypeAPI } from "@/types/api";
import { cn } from "@/utils/utils";
import { useEffect, useState } from "react";

export default function NodeName({
  display_name,
  selected,
  nodeId,
  showNode,
  validationStatus,
  isOutdated,
  beta,
}: {
  display_name?: string;
  selected: boolean;
  nodeId: string;
  showNode: boolean;
  validationStatus: VertexBuildTypeAPI | null;
  isOutdated: boolean;
  beta: boolean;
}) {
  const [inputName, setInputName] = useState(false);
  const [nodeName, setNodeName] = useState(display_name);
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  const setNode = useFlowStore((state) => state.setNode);
  useEffect(() => {
    if (!selected) {
      setInputName(false);
    }
  }, [selected]);

  useEffect(() => {
    setNodeName(display_name);
  }, [display_name]);

  return inputName ? (
    <div className="m-[1px] w-full">
      <Input
        onBlur={() => {
          setInputName(false);
          if (nodeName?.trim() !== "") {
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
          } else {
            setNodeName(display_name);
          }
        }}
        value={nodeName}
        autoFocus
        onChange={(e) => setNodeName(e.target.value)}
        data-testid={`input-title-${display_name}`}
      />
    </div>
  ) : (
    <div className="group flex w-full items-center gap-1">
      <div
        onDoubleClick={(event) => {
          if (!showNode) {
            return;
          }
          setInputName(true);
          takeSnapshot();
          event.stopPropagation();
          event.preventDefault();
        }}
        data-testid={"title-" + display_name}
        className={
          showNode
            ? "nodoubleclick w-full cursor-text truncate font-medium text-primary"
            : "cursor-default"
        }
      >
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "max-w-44 truncate text-[14px]",
              validationStatus?.data?.duration && "max-w-36",
              validationStatus?.data?.duration && beta && "max-w-20",
              isOutdated && "max-w-40",
              !showNode && "max-w-28",
            )}
          >
            {display_name}
          </span>
        </div>
      </div>
    </div>
  );
}
