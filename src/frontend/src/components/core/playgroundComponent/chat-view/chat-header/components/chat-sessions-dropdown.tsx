import React, { useState } from "react";
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
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

export function ChatSessionsDropdown({
  sessions,
  onNewChat,
  onSessionSelect,
  currentSessionId,
  open: controlledOpen,
  onOpenChange: controlledOnOpenChange,
}: ChatSessionsDropdownProps) {
  const currentFlowId = useGetFlowId();
  const hasSessions: boolean = sessions.length > 0;
  const [internalOpen, setInternalOpen] = useState(false);

  // Use controlled state if provided, otherwise use internal state
  const open = controlledOpen !== undefined ? controlledOpen : internalOpen;
  const setOpen = controlledOnOpenChange || setInternalOpen;

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 rounded"
          aria-label="Chat sessions"
          data-testid="session-selector-trigger"
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
                  onSelect={() => {
                    onSessionSelect?.(session);
                    setOpen(false);
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
                onSelect={() => {
                  onNewChat?.();
                  setOpen(false);
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
            onSelect={() => {
              onNewChat?.();
              setOpen(false);
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
