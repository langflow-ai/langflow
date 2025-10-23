import { AnimatedConditional } from "@/components/ui/animated-close";
import { useIsMobile } from "@/hooks/use-mobile";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import ChatView from "./components/chatView/chat-view";
import { PlaygroundHeader } from "./components/playgroundHeader/playground-header";
import SessionSidebar from "./components/sessionSidebar/session-sidebar";

export function PlaygroundComponent(): JSX.Element {
  const isFullscreen = usePlaygroundStore((state) => state.isFullscreen);

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
        <div className="flex flex-grow overflow-hidden">
          <ChatView />
        </div>
      </div>
    </div>
  );
}
