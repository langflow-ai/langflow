import { useEffect, useRef, useState } from "react";
import { useNodes } from "reactflow";
import { CHAT_FORM_DIALOG_SUBTITLE } from "../../constants/constants";
import BaseModal from "../../modals/baseModal";
import useFlowStore from "../../stores/flowStore";
import { ChatType } from "../../types/chat";
import { NodeType } from "../../types/flow";
import IOView from "../IOview";
import ChatTrigger from "../ViewTriggers/chat";
import IconComponent from "../genericIconComponent";
import BuildTrigger from "./buildTrigger";

export default function Chat({ flow }: ChatType): JSX.Element {
  const [open, setOpen] = useState(false);
  const flowState = useFlowStore((state) => state.flowState);
  const checkInputAndOutput = useFlowStore(
    (state) => state.checkInputAndOutput
  );
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (
        (event.key === "K" || event.key === "k") &&
        (event.metaKey || event.ctrlKey) &&
        checkInputAndOutput()
      ) {
        event.preventDefault();
        setOpen((oldState) => !oldState);
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  const prevNodesRef = useRef<any[] | undefined>();
  const nodes: NodeType[] = useNodes();

  return (
    <>
      <div className="flex flex-col">
        <BuildTrigger open={open} flow={flow} />
        {checkInputAndOutput() && (
          <BaseModal open={open} setOpen={setOpen}>
            <BaseModal.Trigger asChild>
              <ChatTrigger />
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
