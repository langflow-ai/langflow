import { useEffect, useRef, useState } from "react";
import type { ChatMessageType } from "@/types/chat";

// Assistant text streams in by mutating the last message, so a live region
// over the message list would re-announce on every token. The list only
// announces additions (and is aria-busy while building); this cue counts
// builds that settle on an assistant reply so a separate status region can
// announce a short "done" message without duplicating the response body into
// the DOM.
export function useResponseCompleteCue(
  isBuilding: boolean,
  chatHistory: ChatMessageType[] | undefined,
): number {
  const [completedCount, setCompletedCount] = useState(0);
  const wasBuildingRef = useRef(isBuilding);
  useEffect(() => {
    if (wasBuildingRef.current && !isBuilding) {
      const lastMessage = chatHistory?.[chatHistory.length - 1];
      if (lastMessage && !lastMessage.isSend) {
        setCompletedCount((count) => count + 1);
      }
    }
    wasBuildingRef.current = isBuilding;
  }, [isBuilding, chatHistory]);
  return completedCount;
}
