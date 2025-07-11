import { useUtilityStore } from "@/stores/utilityStore";
import { type ChatMessageType, ChatType } from "@/types/chat";
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

      if (trackVisibility.category === "error") {
        scrollRef.current.scrollIntoView({
          behavior: playgroundScrollBehaves,
        });
        setTimeout(() => {
          if (!scrollRef.current) return;
          scrollRef.current.scrollIntoView({
            behavior: "smooth",
          });
        }, 400);
      } else {
        scrollRef.current.scrollIntoView({
          behavior: playgroundScrollBehaves,
        });
        if (playgroundScrollBehaves === "smooth") {
          setPlaygroundScrollBehaves("instant");
          setTimeout(() => {
            if (!scrollRef.current) return;
            scrollRef.current.scrollIntoView({
              behavior: "instant",
            });
          }, 200);
        }
      }
    }
  }, [trackVisibility]);

  return <div ref={scrollRef} className="h-px w-full" />;
}
