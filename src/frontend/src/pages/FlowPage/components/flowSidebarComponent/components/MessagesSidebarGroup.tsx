import { useCallback, useEffect, useMemo } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { useGetMessagesQuery } from "@/controllers/API/queries/messages";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { cn } from "@/utils/utils";

interface MessagesSidebarGroupProps {
  selectedSessionId: string | null;
  onSelectSession: (id: string | null) => void;
}

interface SessionData {
  id: string;
  messageCount: number;
  lastMessage: string;
  lastTimestamp: string;
}

/**
 * Empty state component when no sessions are available
 */
const SessionsEmptyState = () => {
  return (
    <div className="flex h-full min-h-[200px] w-full flex-col items-center justify-center px-4 py-8 text-center">
      <IconComponent
        name="MessagesSquare"
        className="mb-3 h-10 w-10 text-muted-foreground opacity-50"
      />
      <p className="text-sm text-muted-foreground">No sessions yet</p>
      <p className="mt-1 text-xs text-muted-foreground">
        Run your flow to see sessions here
      </p>
    </div>
  );
};

/**
 * Loading state component
 */
const SessionsLoadingState = () => {
  return (
    <div className="flex h-full min-h-[100px] w-full items-center justify-center">
      <IconComponent
        name="Loader2"
        className="h-6 w-6 animate-spin text-muted-foreground"
      />
    </div>
  );
};

/**
 * Format timestamp to relative time
 */
const formatTimestamp = (timestamp: string) => {
  if (!timestamp) return "";

  try {
    const date = new Date(timestamp);
    if (isNaN(date.getTime())) return "";

    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return "just now";
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    return date.toLocaleDateString();
  } catch {
    return "";
  }
};

/**
 * Truncate text to max length
 */
const truncateText = (text: string, maxLength: number = 20) => {
  if (!text) return "";
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + "...";
};

/**
 * Individual session item in the list
 */
const SessionListItem = ({
  session,
  isSelected,
  onSelect,
}: {
  session: SessionData;
  isSelected: boolean;
  onSelect: () => void;
}) => {
  return (
    <button
      onClick={onSelect}
      className={cn(
        "flex w-full flex-col gap-1 rounded-md px-2 py-2 text-left transition-colors",
        isSelected
          ? "bg-accent text-accent-foreground"
          : "hover:bg-accent/50 text-foreground",
      )}
    >
      <div className="flex w-full items-center justify-between gap-2">
        <span className="truncate text-xs font-medium">
          {truncateText(session.id, 20) || "Default Session"}
        </span>
        <span className="shrink-0 text-[10px] text-muted-foreground">
          {formatTimestamp(session.lastTimestamp)}
        </span>
      </div>
      <div className="flex w-full items-center justify-between gap-2">
        <span className="truncate text-xs text-muted-foreground">
          {truncateText(session.lastMessage, 30)}
        </span>
        <span className="shrink-0 rounded-full bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
          {session.messageCount}
        </span>
      </div>
    </button>
  );
};

/**
 * Sidebar group for messages - shows list of sessions
 * Each session can be selected to view its messages in the main content area
 */
const MessagesSidebarGroup = ({
  selectedSessionId,
  onSelectSession,
}: MessagesSidebarGroupProps) => {
  const { setActiveSection, open, toggleSidebar } = useSidebar();
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);

  // Fetch messages for the current flow
  const { data: messagesData, isLoading } = useGetMessagesQuery(
    { id: currentFlowId ?? undefined, mode: "union" },
    { enabled: !!currentFlowId },
  );

  // Group messages by session_id
  const sessions: SessionData[] = useMemo(() => {
    const messages = (messagesData?.rows as any)?.data ?? [];
    if (!messages.length) return [];

    const sessionMap = new Map<string, any[]>();

    messages.forEach((msg: any) => {
      const sessionId = msg.session_id || "";
      if (!sessionMap.has(sessionId)) {
        sessionMap.set(sessionId, []);
      }
      sessionMap.get(sessionId)!.push(msg);
    });

    return Array.from(sessionMap.entries())
      .map(([sessionId, msgs]) => {
        // Sort messages by timestamp to get the latest
        const sortedMsgs = [...msgs].sort(
          (a, b) =>
            new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
        );
        const lastMsg = sortedMsgs[0];

        return {
          id: sessionId,
          messageCount: msgs.length,
          lastMessage: lastMsg?.text || "",
          lastTimestamp: lastMsg?.timestamp || "",
        };
      })
      .sort(
        (a, b) =>
          new Date(b.lastTimestamp).getTime() -
          new Date(a.lastTimestamp).getTime(),
      );
  }, [messagesData]);

  // Auto-select first session when data loads
  useEffect(() => {
    if (sessions.length > 0 && selectedSessionId === null) {
      onSelectSession(sessions[0].id);
    }
  }, [sessions, selectedSessionId, onSelectSession]);

  const handleClose = useCallback(() => {
    setActiveSection("components");
    if (!open) {
      toggleSidebar();
    }
  }, [setActiveSection, open, toggleSidebar]);

  const hasSessions = sessions.length > 0;

  return (
    <SidebarGroup className={`p-3 pr-2${!hasSessions ? " h-full" : ""}`}>
      <SidebarGroupLabel className="flex w-full cursor-default items-center justify-between">
        <span>Sessions</span>
        <Button
          variant="ghost"
          size="icon"
          onClick={handleClose}
          className="h-6 w-6"
          data-testid="close-messages-sidebar"
        >
          <IconComponent name="X" className="h-4 w-4" />
        </Button>
      </SidebarGroupLabel>
      <SidebarGroupContent className="h-full overflow-y-auto">
        {isLoading && <SessionsLoadingState />}
        {!isLoading && !hasSessions && <SessionsEmptyState />}
        {!isLoading && hasSessions && (
          <SidebarMenu>
            {sessions.map((session) => (
              <SidebarMenuItem key={session.id || "default"}>
                <SessionListItem
                  session={session}
                  isSelected={selectedSessionId === session.id}
                  onSelect={() => onSelectSession(session.id)}
                />
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        )}
      </SidebarGroupContent>
    </SidebarGroup>
  );
};

export default MessagesSidebarGroup;
