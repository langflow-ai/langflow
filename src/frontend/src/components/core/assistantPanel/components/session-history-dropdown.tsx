/**
 * Dropdown showing saved assistant sessions with switch and delete actions.
 */

import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/utils/utils";
import moment from "moment";
import type { SessionHistoryEntry } from "../assistant-panel.types";

interface SessionHistoryDropdownProps {
  sessions: SessionHistoryEntry[];
  activeSessionId: string;
  onSelectSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
  isExpanded?: boolean;
}

export function SessionHistoryDropdown({
  sessions,
  activeSessionId,
  onSelectSession,
  onDeleteSession,
  isExpanded = false,
}: SessionHistoryDropdownProps) {
  const hasSessions = sessions.length > 0;
  // Expanded panel (has messages / height > min) → dropdown grows down; compact → grows up
  const dropAlign = isExpanded ? "start" : "end";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          title="Session history"
          data-testid="assistant-session-history"
          disabled={!hasSessions}
        >
          <ForwardedIconComponent
            name="History"
            className="h-4 w-4 text-muted-foreground"
          />
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        align="end"
        side="bottom"
        sideOffset={4}
        className="z-[70] max-h-80 w-72 overflow-y-auto"
      >
        <DropdownMenuLabel className="flex items-center gap-1.5 text-xs font-semibold">
          Session History
          <ShadTooltip
            content="Sessions are stored in your browser only and will not be preserved across different browsers or after clearing browser data."
            side="right"
          >
            <div>
              <ForwardedIconComponent
                name="Info"
                className="h-3 w-3 cursor-pointer text-muted-foreground hover:text-foreground"
              />
            </div>
          </ShadTooltip>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />

        {!hasSessions ? (
          <div className="px-2 py-3 text-center text-xs text-muted-foreground">
            No previous sessions
          </div>
        ) : (
          sessions.map((entry) => {
            const isActive = entry.sessionId === activeSessionId;
            return (
              <DropdownMenuItem
                key={entry.sessionId}
                className={cn(
                  "flex cursor-pointer items-center gap-2 px-2 py-2",
                  isActive && "bg-accent",
                )}
                onSelect={() => {
                  if (!isActive) onSelectSession(entry.sessionId);
                }}
              >
                <ForwardedIconComponent
                  name="MessageSquare"
                  className="h-3.5 w-3.5 shrink-0 text-muted-foreground"
                />
                <div className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate text-xs">
                    {entry.firstUserMessage}
                  </span>
                  <span className="text-[10px] text-muted-foreground">
                    {entry.messageCount} msgs
                    {" · "}
                    {moment(entry.lastActiveAt).fromNow()}
                  </span>
                </div>
                <button
                  className="shrink-0 rounded p-0.5 text-muted-foreground hover:text-foreground"
                  data-testid={`delete-session-${entry.sessionId}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    e.preventDefault();
                    onDeleteSession(entry.sessionId);
                  }}
                >
                  <ForwardedIconComponent
                    name="Trash2"
                    className="h-3.5 w-3.5"
                  />
                </button>
              </DropdownMenuItem>
            );
          })
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
