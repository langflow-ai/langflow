import { useContext, useEffect, useRef, useState } from "react";
import { useNodes } from "reactflow";
import { ChatType } from "../../types/chat";
import ChatTrigger from "./chatTrigger";

import * as _ from "lodash";
import { CHAT_FORM_DIALOG_SUBTITLE } from "../../constants/constants";
import { flowManagerContext } from "../../contexts/flowManagerContext";
import { FlowsContext } from "../../contexts/flowsContext";
import BaseModal from "../../modals/baseModal";
import { NodeType } from "../../types/flow";
import IOView from "../IOview";
import IconComponent from "../genericIconComponent";

export default function Chat({ flow }: ChatType): JSX.Element {
  const [open, setOpen] = useState(false);
  const [canOpen, setCanOpen] = useState(false);
  const { tabsState } = useContext(FlowsContext);
  const { showPanel, isBuilt, setIsBuilt } = useContext(flowManagerContext);
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

  // useEffect(() => {
  //   // Define an async function within the useEffect hook
  //   const fetchBuildStatus = async () => {
  //     const response = await getBuildStatus(flow.id);
  //     setIsBuilt(response.data.built);
  //   };

  //   // Call the async function
  //   fetchBuildStatus();
  // }, [flow]);

  const prevNodesRef = useRef<any[] | undefined>();
  const nodes: NodeType[] = useNodes();
  useEffect(() => {
    const prevNodes = prevNodesRef.current;
    const currentNodes = nodes.map((node: NodeType) =>
      _.cloneDeep(node.data.node?.template)
    );
    if (
      tabsState &&
      tabsState[flow.id] &&
      tabsState[flow.id].isPending &&
      JSON.stringify(prevNodes) !== JSON.stringify(currentNodes)
    ) {
      setIsBuilt(false);
    }
    if (
      tabsState &&
      tabsState[flow.id] &&
      tabsState[flow.id].formKeysData &&
      tabsState[flow.id].formKeysData.input_keys !== null
    ) {
      setCanOpen(true);
    } else {
      setCanOpen(false);
    }

    prevNodesRef.current = currentNodes;
  }, [tabsState, flow.id]);

  return (
    <>
      <div className="flex flex-col">
        {/* <BuildTrigger
          open={open}
          flow={flow}
          setIsBuilt={setIsBuilt}
          isBuilt={isBuilt}
        /> */}
        {showPanel && (
          <BaseModal open={open} setOpen={setOpen}>
            <BaseModal.Trigger asChild>
              <ChatTrigger
                canOpen={canOpen}
                open={open}
                setOpen={setOpen}
                isBuilt={isBuilt}
              />
            </BaseModal.Trigger>
            {/* TODO ADAPT TO ALL TYPES OF INPUTS AND OUTPUTS */}
            <BaseModal.Header description={CHAT_FORM_DIALOG_SUBTITLE}>
              <div className="flex items-center">
                <span className="pr-2">Chat</span>
                <IconComponent
                  name="prompts"
                  className="h-6 w-6 pl-1 text-foreground"
                  aria-hidden="true"
                />
              </div>
            </BaseModal.Header>
            <BaseModal.Content>
              <IOView />
            </BaseModal.Content>
          </BaseModal>
        )}
      </div>
    </>
  );
}
