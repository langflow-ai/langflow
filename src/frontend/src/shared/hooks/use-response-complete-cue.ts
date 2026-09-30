import { useEffect, useRef, useState } from "react";
import type { ChatMessageType } from "@/types/chat";

export interface ResponseCompleteCue {
  completedCount: number;
  completedText: string;
  isAnnouncing: boolean;
}

// How long the completed reply stays in the live region before it is blanked.
// A screen reader captures a live region's text at the moment it changes, so
// clearing it afterwards doesn't retract the announcement — but it does stop
// the reply from outliving what it describes: without this the text sat in the
// accessibility tree indefinitely (still there after its own session was
// deleted) and duplicated every transcript string page-wide.
const ANNOUNCEMENT_TTL_MS = 2000;

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
    isAnnouncing: false,
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
          isAnnouncing: true,
        }));
      }
    }
    wasBuildingRef.current = isBuilding;
  }, [isBuilding, chatHistory]);

  // Retire the announcement once it has had time to be spoken. completedCount
  // stays monotonic across retirements so ResponseCompleteStatus keeps
  // alternating its trailing space for back-to-back identical replies.
  useEffect(() => {
    if (!cue.isAnnouncing) return;
    const timer = setTimeout(() => {
      setCue((previous) => ({
        ...previous,
        completedText: "",
        isAnnouncing: false,
      }));
    }, ANNOUNCEMENT_TTL_MS);
    return () => clearTimeout(timer);
  }, [cue.isAnnouncing, cue.completedCount]);

  return cue;
}
