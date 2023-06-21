import { useEffect, useRef, useState } from "react";
import { useNodes } from "reactflow";
import { ChatType } from "../../types/chat";
import ChatTrigger from "./chatTrigger";
import BuildTrigger from "./buildTrigger";
import ChatModal from "../../modals/chatModal";

import { getBuildStatus } from "../../controllers/API";
import { NodeType } from "../../types/flow";

export default function Chat({ flow }: ChatType) {
  const [open, setOpen] = useState(false);
  const [isBuilt, setIsBuilt] = useState(false);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (
        (event.key === "K" || event.key === "k") &&
        (event.metaKey || event.ctrlKey) &&
        isBuilt
      ) {
        event.preventDefault();
        setOpen((oldState) => !oldState);
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isBuilt]);

  useEffect(() => {
    // Define an async function within the useEffect hook
    const fetchBuildStatus = async () => {
      const response = await getBuildStatus(flow.id);
      setIsBuilt(response.built);
    };

    // Call the async function
    fetchBuildStatus();
  }, [flow]);

  const prevNodesRef = useRef<any[] | undefined>();
  const nodes = useNodes();
  useEffect(() => {
    const prevNodes = prevNodesRef.current;
    const currentNodes = nodes.map(
      (node: NodeType) => node.data.node.template.value
    );

    if (
      prevNodes &&
      JSON.stringify(prevNodes) !== JSON.stringify(currentNodes)
    ) {
      setIsBuilt(false);
    }

    prevNodesRef.current = currentNodes;
  }, [nodes]);

  return (
    <>
      {isBuilt ? (
        <div>
          <BuildTrigger
            open={open}
            flow={flow}
            setIsBuilt={setIsBuilt}
            isBuilt={isBuilt}
          />
          <ChatModal key={flow.id} flow={flow} open={open} setOpen={setOpen} />
          <ChatTrigger open={open} setOpen={setOpen} isBuilt={isBuilt} />
        </div>
      ) : (
        <BuildTrigger
          open={open}
          flow={flow}
          setIsBuilt={setIsBuilt}
          isBuilt={isBuilt}
        />
      )}
    </>
  );
}
