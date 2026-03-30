import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import {
  ASSISTANT_MAX_SESSIONS,
  ASSISTANT_TAB_BAR_MIN_WIDTH,
  ASSISTANT_TITLE,
} from "../assistant-panel.constants";
import type { SessionHistoryEntry } from "../assistant-panel.types";
import { SessionHistoryDropdown } from "./session-history-dropdown";
import { SessionTabBar } from "./session-tab-bar";

interface AssistantHeaderProps {
  onClose: () => void;
  onNewSession: () => void;
  hasMessages: boolean;
  sessions: SessionHistoryEntry[];
  activeSessionId: string;
  onSelectSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
  isExpanded: boolean;
  panelWidth: number;
}

export function AssistantHeader({
  onClose,
  onNewSession,
  hasMessages,
  sessions,
  activeSessionId,
  onSelectSession,
  onDeleteSession,
  isExpanded,
  panelWidth,
}: AssistantHeaderProps) {
  const isAtSessionLimit = sessions.length >= ASSISTANT_MAX_SESSIONS;
  const isNewSessionDisabled = !hasMessages || isAtSessionLimit;
  const useTabBar = panelWidth >= ASSISTANT_TAB_BAR_MIN_WIDTH;

  return (
    <div className="flex h-12 items-center gap-1 px-2">
      {/* Title — shrinks to make room for tabs */}
      <h2 className="shrink-0 pl-2 text-sm font-medium text-foreground">
        {ASSISTANT_TITLE}
      </h2>

      {/* Tabs inline — fill available space between title and buttons */}
      {useTabBar ? (
        <SessionTabBar
          sessions={sessions}
          activeSessionId={activeSessionId}
          hasMessages={hasMessages}
          onSelectSession={onSelectSession}
          onDeleteSession={onDeleteSession}
          onNewSession={onNewSession}
        />
      ) : (
        <>
          {/* Spacer to push buttons right when no tabs */}
          <div className="flex-1" />
          <ShadTooltip
            content={
              isAtSessionLimit
                ? `Maximum of ${ASSISTANT_MAX_SESSIONS} sessions reached. Delete a session to create a new one.`
                : ""
            }
            side="bottom"
            avoidCollisions={false}
          >
            <span className="inline-flex">
              <Button
                variant="ghost"
                size="sm"
                data-testid="assistant-new-session"
                className="h-8 gap-1.5 px-2 text-sm text-muted-foreground hover:text-foreground"
                onClick={onNewSession}
                disabled={isNewSessionDisabled}
              >
                <ForwardedIconComponent
                  name={isAtSessionLimit ? "AlertCircle" : "Plus"}
                  className="h-4 w-4"
                />
                {isAtSessionLimit ? "Max sessions" : "New session"}
              </Button>
            </span>
          </ShadTooltip>

          <SessionHistoryDropdown
            sessions={sessions}
            activeSessionId={activeSessionId}
            onSelectSession={onSelectSession}
            onDeleteSession={onDeleteSession}
            isExpanded={isExpanded}
          />
        </>
      )}

      {/* New session button — shown next to close when in tab mode */}
      {useTabBar && (
        <ShadTooltip
          content={
            isAtSessionLimit
              ? `Max ${ASSISTANT_MAX_SESSIONS} sessions`
              : ""
          }
          side="bottom"
        >
          <span className="inline-flex">
            <Button
              variant="ghost"
              size="sm"
              data-testid="tab-new-session"
              className="h-8 shrink-0 gap-1 px-2 text-xs text-muted-foreground hover:text-foreground"
              onClick={onNewSession}
              disabled={isNewSessionDisabled}
            >
              <ForwardedIconComponent name="Plus" className="h-3.5 w-3.5" />
              New
            </Button>
          </span>
        </ShadTooltip>
      )}

      {/* Close button — always visible */}
      <Button
        variant="ghost"
        size="icon"
        data-testid="assistant-close"
        className="h-8 w-8 shrink-0"
        title="Close"
        onClick={onClose}
      >
        <ForwardedIconComponent
          name="X"
          className="h-4 w-4 text-muted-foreground"
        />
      </Button>
    </div>
  );
}
