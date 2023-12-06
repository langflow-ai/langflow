import { useEffect, useState } from "react";
import { NodeToolbar } from "reactflow";
import { GradientGroup } from "../../../../icons/GradientSparkles";
export default function SelectionMenu({ onClick, nodes, isVisible }) {
  const [isOpen, setIsOpen] = useState(false);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [lastNodes, setLastNodes] = useState(nodes);

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
            className="flex h-full w-full items-center justify-between text-sm hover:text-indigo-500"
            onClick={onClick}
          >
            <GradientGroup
              strokeWidth={1.5}
              size={22}
              className="text-primary"
            />
            Group
          </button>
        </div>
      </div>
    </NodeToolbar>
  );
}
