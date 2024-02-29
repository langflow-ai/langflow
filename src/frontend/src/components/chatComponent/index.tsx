import { useEffect, useRef, useState } from "react";
import useFlowStore from "../../stores/flowStore";
import { ChatType } from "../../types/chat";
import IOView from "../IOview";
import ChatTrigger from "../ViewTriggers/chat";

export default function Chat(): JSX.Element {
  const [open, setOpen] = useState(false);
  const hasIO = useFlowStore((state) => state.hasIO);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (
        (event.key === "K" || event.key === "k") &&
        (event.metaKey || event.ctrlKey) &&
        useFlowStore.getState().hasIO
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
      <div className="flex flex-col">
        {hasIO && (
          <IOView open={open} setOpen={setOpen}>
            <ChatTrigger />
          </IOView>
        )}
      </div>
    </>
  );
}
