import { useEffect, useState } from "react";
import { NodeToolbar } from "reactflow";
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
  const [disable, setDisable] = useState<boolean>(
    lastSelection && edges.length > 0
      ? validateSelection(lastSelection!, edges).length > 0
      : false,
  );
  const [isOpen, setIsOpen] = useState(false);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [lastNodes, setLastNodes] = useState(nodes);

  useEffect(() => {
    if (isOpen) {
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
            "duration-400 h-10 w-24 rounded-md border border-indigo-300 bg-background px-2.5 text-primary shadow-inner transition-all ease-in-out" +
            (isTransitioning ? " opacity-100" : " opacity-0 ")
          }
        >
          <button
            className={`${
              disable
                ? "flex h-full w-full cursor-not-allowed items-center justify-between text-sm text-muted-foreground"
                : "flex h-full w-full items-center justify-between text-sm"
            }`}
            onClick={onClick}
            disabled={disable}
          >
            <GradientGroup
              strokeWidth={1.5}
              size={22}
              className="text-primary"
              disabled={disable}
            />
            Group
          </button>
        </div>
      </div>
    </NodeToolbar>
  );
}
