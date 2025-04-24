import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/utils/utils";
import IconComponent from "../../../components/common/genericIconComponent";
import { ChatViewWrapperProps } from "../types/chat-view-wrapper";
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
      <div
        className={cn(
          "mb-4 flex h-[5%] items-center text-base font-semibold",
          playgroundPage ? "justify-between" : "lg:justify-start",
        )}
      >
        <div className={cn(sidebarOpen ? "lg:hidden" : "left-4")}>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setSidebarOpen(true)}
              className="h-8 w-8"
            >
              <IconComponent
                name="PanelLeftOpen"
                className="h-[18px] w-[18px] text-ring"
              />
            </Button>
          </div>
        </div>
        {visibleSession && sessions.length > 0 && (
          <div
            className={cn(
              "truncate text-center font-semibold",
              playgroundPage ? "" : "mr-12 flex-grow lg:mr-0",
              sidebarOpen ? "blur-sm lg:blur-0" : "",
            )}
          >
            {visibleSession === currentFlowId
              ? "Default Session"
              : `${visibleSession}`}
          </div>
        )}
        <div
          className={cn(
            sidebarOpen ? "pointer-events-none opacity-0" : "",
            "flex items-center justify-center rounded-sm ring-offset-background transition-opacity focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
            playgroundPage ? "right-2 top-4" : "absolute right-12 top-2 h-8",
          )}
        >
          <ShadTooltip side="bottom" styleClasses="z-50" content="New Chat">
            <Button
              className="mr-2 h-[32px] w-[32px] hover:bg-secondary-hover"
              variant="ghost"
              size="icon"
              onClick={() => {
                setvisibleSession(undefined);
                setSelectedViewField(undefined);
              }}
            >
              <IconComponent
                name="Plus"
                className="!h-[18px] !w-[18px] text-ring"
              />
            </Button>
          </ShadTooltip>
          {!playgroundPage && <Separator orientation="vertical" />}
        </div>
      </div>

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
