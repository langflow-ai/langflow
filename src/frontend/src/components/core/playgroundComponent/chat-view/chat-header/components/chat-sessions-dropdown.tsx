import React, { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";
import { cn } from "@/utils/utils";
import { useGetFlowId } from "../../hooks/use-get-flow-id";

interface ChatSessionsDropdownProps {
  onNewChat?: () => void;
  onSessionSelect?: (sessionId: string) => void;
  currentSessionId?: string;
}

export function ChatSessionsDropdown({
  onNewChat,
  onSessionSelect,
  currentSessionId,
}: ChatSessionsDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const currentFlowId = useGetFlowId();
  const { data: sessionsData, isLoading } = useGetSessionsFromFlowQuery({
    id: currentFlowId,
  });

  const sessions = sessionsData?.sessions || [];
  const hasSessions = sessions.length > 0;

  const handleSessionClick = (sessionId: string) => {
    onSessionSelect?.(sessionId);
    setIsOpen(false);
  };

  const handleNewChatClick = () => {
    onNewChat?.();
    setIsOpen(false);
  };

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="p-2 hover:bg-accent rounded transition-colors"
        aria-label="Chat sessions"
        aria-expanded={isOpen}
      >
        <ForwardedIconComponent name="ListRestart" className="h-4 w-4" />
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />
          <div className="absolute left-0 top-full mt-2 w-64 bg-background border rounded-md shadow-lg z-20 max-h-96 overflow-y-auto">
            {isLoading ? (
              <div className="p-4 text-sm text-muted-foreground">
                Loading...
              </div>
            ) : hasSessions ? (
              <>
                {sessions.map((session, index) => (
                  <button
                    key={session}
                    onClick={() => handleSessionClick(session)}
                    className={cn(
                      "w-full text-left px-4 py-2 text-sm hover:bg-accent transition-colors",
                      index === 0 && "rounded-t-md",
                      currentSessionId === session && "bg-accent font-semibold",
                    )}
                  >
                    {session === currentFlowId ? "Default Session" : session}
                  </button>
                ))}
                <div className="border-t">
                  <button
                    onClick={handleNewChatClick}
                    className="w-full text-left px-4 py-2 text-sm hover:bg-accent transition-colors flex items-center gap-2 rounded-b-md"
                  >
                    <ForwardedIconComponent name="Plus" className="h-4 w-4" />
                    <span>New Chat</span>
                  </button>
                </div>
              </>
            ) : (
              <button
                onClick={handleNewChatClick}
                className="w-full text-left px-4 py-2 text-sm hover:bg-accent transition-colors flex items-center gap-2 rounded-md"
              >
                <ForwardedIconComponent name="Plus" className="h-4 w-4" />
                <span>New Chat</span>
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
