import { useUtilityStore } from "@/stores/utilityStore";
import { ChatMessageType, ChatType } from "@/types/chat";
import { useEffect, useRef } from "react";

interface ChatScrollAnchorProps {
  trackVisibility: ChatMessageType;
  canScroll: boolean;
}

export function ChatScrollAnchor({
  trackVisibility,
  canScroll,
}: ChatScrollAnchorProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  const playgroundScrollBehaves = useUtilityStore(
    (state) => state.playgroundScrollBehaves,
  );
  const setPlaygroundScrollBehaves = useUtilityStore(
    (state) => state.setPlaygroundScrollBehaves,
  );

  useEffect(() => {
    if (canScroll) {
      if (!scrollRef.current) return;

      if (
        playgroundScrollBehaves === "instant" ||
        trackVisibility.category === "error"
      ) {
        scrollRef.current.scrollIntoView({
          behavior: playgroundScrollBehaves,
        });
        setTimeout(() => {
          if (!scrollRef.current) return;
          scrollRef.current.scrollIntoView({
            behavior: "smooth",
          });
        }, 400);
        setPlaygroundScrollBehaves("smooth");
      } else {
        scrollRef.current.scrollIntoView({
          behavior: playgroundScrollBehaves,
        });
      }
    }
  }, [canScroll, trackVisibility]);

  return <div ref={scrollRef} className="h-px w-full" />;
}
