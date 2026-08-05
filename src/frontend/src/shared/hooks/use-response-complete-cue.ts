import { useEffect, useRef, useState } from "react";
import type { ChatMessageType } from "@/types/chat";

export interface ResponseCompleteCue {
  completedCount: number;
  completedText: string;
}

// Assistant text streams in by mutating the last message, so a live region
// over the message list would either spam every token or (with
// aria-relevant="additions") never announce the reply at all. This cue
// watches builds that settle on an assistant reply and captures the reply's
// final text so a separate status region can announce the completed response
// once — the screen reader hears the answer without the transcript itself
// being live (LE-2041 QA).
export function useResponseCompleteCue(
  isBuilding: boolean,
  chatHistory: ChatMessageType[] | undefined,
): ResponseCompleteCue {
  const [cue, setCue] = useState<ResponseCompleteCue>({
    completedCount: 0,
    completedText: "",
  });
  const wasBuildingRef = useRef(isBuilding);
  useEffect(() => {
    if (wasBuildingRef.current && !isBuilding) {
      const lastMessage = chatHistory?.[chatHistory.length - 1];
      if (lastMessage && !lastMessage.isSend) {
        const completedText =
          typeof lastMessage.message === "string" ? lastMessage.message : "";
        setCue((previous) => ({
          completedCount: previous.completedCount + 1,
          completedText,
        }));
      }
    }
    wasBuildingRef.current = isBuilding;
  }, [isBuilding, chatHistory]);
  return cue;
}
