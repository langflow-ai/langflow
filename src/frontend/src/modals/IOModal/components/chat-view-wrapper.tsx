import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/utils/utils";
import IconComponent from "../../../components/common/genericIconComponent";
import { ChatViewWrapperProps } from "../types/chat-view-wrapper";
import ChatView from "./chatView/chat-view";

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
}: ChatViewWrapperProps) => {
  return (
    <div
      className={cn(
        "flex h-full w-full flex-col justify-between p-4",
        selectedViewField ? "hidden" : "",
      )}
    >
      <div className="mb-4 h-[5%] text-[16px] font-semibold">
        {visibleSession && sessions.length > 0 && sidebarOpen && (
          <div className="hidden lg:block">
            {visibleSession === currentFlowId
              ? "Default Session"
              : `${visibleSession}`}
          </div>
        )}
        <div className={cn(sidebarOpen ? "lg:hidden" : "")}>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setSidebarOpen(true)}
              className="h-8 w-8"
            >
              <IconComponent
                name="PanelLeftOpen"
                className="text-ring h-[18px] w-[18px]"
              />
            </Button>
            <div className="font-semibold">Playground</div>
          </div>
        </div>
        <div
          className={cn(
            sidebarOpen ? "pointer-events-none opacity-0" : "",
            "ring-offset-background focus:ring-ring absolute flex h-8 items-center justify-center rounded-sm transition-opacity focus:ring-2 focus:ring-offset-2 focus:outline-hidden",
            isPlayground ? "top-4 right-2" : "top-2 right-12",
          )}
        >
          <ShadTooltip side="bottom" styleClasses="z-50" content="New Chat">
            <Button
              className="hover:bg-secondary-hover mr-2 h-[32px] w-[32px]"
              variant="ghost"
              size="icon"
              onClick={() => {
                setvisibleSession(undefined);
                setSelectedViewField(undefined);
              }}
            >
              <IconComponent
                name="Plus"
                className="text-ring h-[18px]! w-[18px]!"
              />
            </Button>
          </ShadTooltip>
          {!isPlayground && <Separator orientation="vertical" />}
        </div>
      </div>
      <div
        className={cn(
          visibleSession ? "h-[95%]" : "h-full",
          sidebarOpen
            ? "pointer-events-none blur-xs lg:pointer-events-auto lg:blur-none"
            : "",
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
          />
        )}
      </div>
    </div>
  );
};
