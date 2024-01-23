import { useEffect, useRef, useState } from "react";
import { useNodes } from "reactflow";
import { ChatType } from "../../types/chat";
import BuildTrigger from "./buildTrigger";
import ChatTrigger from "./chatTrigger";

import * as _ from "lodash";
import FormModal from "../../modals/formModal";
import useFlowStore from "../../stores/flowStore";
import { NodeType } from "../../types/flow";

export default function Chat({ flow }: ChatType): JSX.Element {
  const [open, setOpen] = useState(false);
  const isBuilt = useFlowStore((state) => state.isBuilt);
  const setIsBuilt = useFlowStore((state) => state.setIsBuilt);
  const flowState = useFlowStore((state) => state.flowState);
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

  const prevNodesRef = useRef<any[] | undefined>();
  const nodes: NodeType[] = useNodes();
  useEffect(() => {
    const prevNodes = prevNodesRef.current;
    const currentNodes = nodes.map((node: NodeType) =>
      _.cloneDeep(node.data.node?.template)
    );
    if (JSON.stringify(prevNodes) !== JSON.stringify(currentNodes)) {
      setIsBuilt(false);
    }
    prevNodesRef.current = currentNodes;
  }, [flowState, flow.id]);

  return (
    <>
      <div>
        <BuildTrigger
          open={open}
          flow={flow}
          setIsBuilt={setIsBuilt}
          isBuilt={isBuilt}
        />
        {isBuilt && flowState && !!flowState?.input_keys && (
          <FormModal key={flow.id} flow={flow} open={open} setOpen={setOpen} />
        )}
        <ChatTrigger
          canOpen={!!flowState?.input_keys}
          open={open}
          setOpen={setOpen}
          isBuilt={isBuilt}
        />
      </div>
    </>
  );
}
