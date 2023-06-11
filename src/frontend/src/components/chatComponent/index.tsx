import { useEffect, useRef, useState } from "react";

import { ChatMessageType, ChatType } from "../../types/chat";
import ChatTrigger from "./chatTrigger";
import BuildTrigger from "./buildTrigger";
import ChatModal from "../../modals/chatModal";

import _ from "lodash";

export default function Chat({ flow }: ChatType) {
  const [open, setOpen] = useState(false);
  const [isBuilt, setIsBuilt] = useState(false);
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (
        (event.key === "K" || event.key === "k") &&
        (event.metaKey || event.ctrlKey)
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
  return (
    <>
      <ChatModal key={flow.id} flow={flow} open={open} setOpen={setOpen} />

      {isBuilt ? (
        <div>
          <BuildTrigger
            open={open}
            flow={flow}
            setIsBuilt={setIsBuilt}
            isBuilt={isBuilt}
          />
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
