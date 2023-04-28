import { useEffect, useRef, useState } from "react";

import { ChatMessageType, ChatType } from "../../types/chat";
import ChatTrigger from "./chatTrigger";
import ChatModal from "../../modals/chatModal";

const _ = require("lodash");

export default function Chat({ flow }: ChatType) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // event.preventDefault()
      if (
        (event.key === "K" || event.key === "k") &&
        (event.metaKey || event.ctrlKey)
      ) {
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
      <ChatTrigger open={open} setOpen={setOpen} flow={flow} />
    </>
  );
}
