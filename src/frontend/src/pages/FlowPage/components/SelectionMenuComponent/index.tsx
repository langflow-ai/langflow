import { NodeToolbar } from "@xyflow/react";
import { useEffect, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import ShadTooltip from "../../../../components/common/shadTooltipComponent";
import { Button } from "../../../../components/ui/button";
import { GradientGroup } from "../../../../icons/GradientSparkles";
import useFlowStore from "../../../../stores/flowStore";
import { validateSelection } from "../../../../utils/reactflowUtils";
export default function SelectionMenu({
  onClick,
  nodes,
  isVisible,
  lastSelection,
}) {
  const edges = useFlowStore((state) => state.edges);
  const unselectAll = useFlowStore((state) => state.unselectAll);
  const [disable, setDisable] = useState<boolean>(
    lastSelection && edges.length > 0
      ? validateSelection(lastSelection!, edges).length > 0
      : false,
  );
  const [errors, setErrors] = useState<string[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [lastNodes, setLastNodes] = useState(nodes);

  useHotkeys("esc", unselectAll, { preventDefault: true });

  useEffect(() => {
    if (isOpen) {
      setErrors(validateSelection(lastSelection!, edges));
      return setDisable(validateSelection(lastSelection!, edges).length > 0);
    }
    setDisable(false);
  }, [isOpen, setIsOpen]);

  // nodes get saved to not be gone after the toolbar closes
  useEffect(() => {
    setLastNodes(nodes);
  }, [isOpen]);

  // transition starts after and ends before the toolbar closes
  useEffect(() => {
    if (isVisible) {
      setIsOpen(true);
      setTimeout(() => {
        setIsTransitioning(true);
      }, 50);
    } else {
      setIsTransitioning(false);
      setTimeout(() => {
        setIsOpen(false);
      }, 500);
    }
  }, [isVisible]);

  return (
    <NodeToolbar
      isVisible={isOpen}
      offset={5}
      nodeId={
        lastNodes && lastNodes.length > 0 ? lastNodes.map((n) => n.id) : []
      }
    >
      <div className="h-10 w-28 overflow-hidden">
        <div
          className={
            "bg-background text-primary h-10 w-24 rounded-md border border-indigo-300 px-2.5 shadow-inner transition-all duration-400 ease-in-out" +
            (isTransitioning ? " opacity-100" : " opacity-0")
          }
        >
          {errors.length > 0 ? (
            <ShadTooltip content={errors[0]} side={"top"}>
              <Button
                unstyled
                className={`${
                  disable
                    ? "text-muted-foreground flex h-full w-full cursor-not-allowed items-center justify-between text-sm"
                    : "flex h-full w-full items-center justify-between text-sm"
                }`}
                onClick={onClick}
                disabled={disable}
                data-testid="error-group-node"
              >
                <GradientGroup
                  strokeWidth={1.5}
                  size={22}
                  className="text-primary"
                  disabled={disable}
                />
                Group
              </Button>
            </ShadTooltip>
          ) : (
            <Button
              unstyled
              className={`${
                disable
                  ? "text-muted-foreground flex h-full w-full cursor-not-allowed items-center justify-between text-sm"
                  : "flex h-full w-full items-center justify-between text-sm"
              }`}
              onClick={onClick}
              disabled={disable}
              data-testid="group-node"
            >
              <GradientGroup
                strokeWidth={1.5}
                size={22}
                className="text-primary"
                disabled={disable}
              />
              Group
            </Button>
          )}
        </div>
      </div>
    </NodeToolbar>
  );
}
