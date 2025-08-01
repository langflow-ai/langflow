import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/utils/utils";
import IconComponent from "../../../components/common/genericIconComponent";
import type { ChatViewWrapperProps } from "../types/chat-view-wrapper";
import ChatView from "./chatView/components/chat-view";

export const ChatViewWrapper = ({
  selectedViewField,
  visibleSession,
  sessions,
  sidebarOpen,
  currentFlowId,
  setSidebarOpen,
  isPlayground,
  setvisibleSession,
  setSelectedViewField,
  messagesFetched,
  sessionId,
  sendMessage,
  canvasOpen,
  setOpen,
  playgroundTitle,
  playgroundPage,
}: ChatViewWrapperProps) => {
  return (
    <div
      className={cn(
        "flex h-full w-full flex-col justify-between px-4 pb-4 pt-2",
        selectedViewField ? "hidden" : "",
      )}
    >
      

      {messagesFetched && (
        <ChatView
          focusChat={sessionId}
          sendMessage={sendMessage}
          visibleSession={visibleSession}
          closeChat={
            !canvasOpen
              ? undefined
              : () => {
                  setOpen(false);
                }
          }
          playgroundPage={playgroundPage}
          sidebarOpen={sidebarOpen}
        />
      )}
    </div>
  );
};
