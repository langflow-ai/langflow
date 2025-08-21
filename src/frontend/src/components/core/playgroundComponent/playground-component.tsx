import { useEffect } from "react";
import { v5 as uuidv5 } from "uuid";
import { AnimatedConditional } from "@/components/ui/animated-close";
import { useIsMobile } from "@/hooks/use-mobile";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import { useUtilityStore } from "@/stores/utilityStore";
import ChatView from "./components/chatView/components/chat-view";
import { PlaygroundHeader } from "./components/playgroundHeader/playground-header";
import SessionSidebar from "./components/sessionSidebar/session-sidebar";

export function PlaygroundComponent(): JSX.Element {
  const clientId = useUtilityStore((state) => state.clientId);
  const realFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const isPlayground = usePlaygroundStore((state) => state.isPlayground);
  const currentFlowId = isPlayground
    ? uuidv5(`${clientId}_${realFlowId}`, uuidv5.DNS)
    : realFlowId;

  const selectedSession = usePlaygroundStore((state) => state.selectedSession);
  const setSelectedSession = usePlaygroundStore(
    (state) => state.setSelectedSession
  );

  const isFullscreen = usePlaygroundStore((state) => state.isFullscreen);

  useEffect(() => {
    setSelectedSession(currentFlowId);
  }, [currentFlowId, setSelectedSession]);

  const isMobile = useIsMobile();

  const isSessionSidebarVisible = isFullscreen && !isMobile;

  return (
    <div className="flex w-full h-full">
      <AnimatedConditional
        className="flex shrink-0"
        isOpen={isSessionSidebarVisible}
      >
        <SessionSidebar />
      </AnimatedConditional>
      <div className="flex flex-col w-full h-full transition-all duration-300">
        <PlaygroundHeader />
        <div className="flex flex-grow p-4">
          <ChatView
            visibleSession={selectedSession}
            playgroundPage={isPlayground}
          />
        </div>
      </div>
    </div>
  );
}
