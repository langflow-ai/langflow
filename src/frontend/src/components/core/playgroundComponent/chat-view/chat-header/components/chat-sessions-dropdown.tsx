import React from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/utils/utils";
import { useGetFlowId } from "../../../hooks/use-get-flow-id";

interface ChatSessionsDropdownProps {
  sessions: string[];
  onNewChat?: () => void;
  onSessionSelect?: (sessionId: string) => void;
  currentSessionId?: string;
}

export function ChatSessionsDropdown({
  sessions,
  onNewChat,
  onSessionSelect,
  currentSessionId,
}: ChatSessionsDropdownProps) {
  const currentFlowId = useGetFlowId();
  const hasSessions: boolean = sessions.length > 0;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 rounded"
          aria-label="Chat sessions"
        >
          <ForwardedIconComponent name="ListRestart" className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-56">
        {hasSessions ? (
          <>
            <DropdownMenuGroup>
              {sessions.map((session) => (
                <DropdownMenuItem
                  key={session}
                  className={cn(
                    "gap-2 text-sm",
                    currentSessionId === session && "font-semibold bg-accent",
                  )}
                  onSelect={(event) => {
                    event.preventDefault();
                    onSessionSelect?.(session);
                  }}
                >
                  {session === currentFlowId ? "Default Session" : session}
                </DropdownMenuItem>
              ))}
            </DropdownMenuGroup>
            <DropdownMenuSeparator className="!my-0" />
            <DropdownMenuGroup>
              <DropdownMenuItem
                className="gap-2 text-sm"
                onSelect={(event) => {
                  event.preventDefault();
                  onNewChat?.();
                }}
              >
                <ForwardedIconComponent name="Plus" className="h-4 w-4" />
                New Session
              </DropdownMenuItem>
            </DropdownMenuGroup>
          </>
        ) : (
          <DropdownMenuItem
            className="gap-2 text-sm"
            onSelect={(event) => {
              event.preventDefault();
              onNewChat?.();
            }}
          >
            <ForwardedIconComponent name="Plus" className="h-4 w-4" />
            New Session
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
