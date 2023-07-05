import { useContext, useEffect, useRef, useState } from "react";
import { useNodes } from "reactflow";
import { ChatType } from "../../types/chat";
import ChatTrigger from "./chatTrigger";
import BuildTrigger from "./buildTrigger";

import { getBuildStatus } from "../../controllers/API";
import { NodeType } from "../../types/flow";
import FormModal from "../../modals/formModal";
import { TabsContext } from "../../contexts/tabsContext";
import * as _ from "lodash";

export default function Chat({ flow }: ChatType) {
  const [open, setOpen] = useState(false);
  const [isBuilt, setIsBuilt] = useState(false);
  const { tabsState } = useContext(TabsContext);

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
    const currentNodes = nodes.map((node: NodeType) =>
      _.cloneDeep(node.data.node.template)
    );
    if (
      tabsState &&
      tabsState[flow.id] &&
      tabsState[flow.id].isPending &&
      JSON.stringify(prevNodes) !== JSON.stringify(currentNodes)
    ) {
      setIsBuilt(false);
    }

    prevNodesRef.current = currentNodes;
  }, [tabsState]);

  return (
    <>
      <div>
        <BuildTrigger
          open={open}
          flow={flow}
          setIsBuilt={setIsBuilt}
          isBuilt={isBuilt}
        />
        {isBuilt && (
          <FormModal key={flow.id} flow={flow} open={open} setOpen={setOpen} />
        )}
        <ChatTrigger open={open} setOpen={setOpen} isBuilt={isBuilt} />
      </div>
    </>
  );
}
