import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { ASSISTANT_MAX_SESSIONS } from "../assistant-panel.constants";
import type { SessionHistoryEntry } from "../assistant-panel.types";
import { SessionHistoryDropdown } from "./session-history-dropdown";

interface AssistantHeaderProps {
  onClose: () => void;
  onNewSession: () => void;
  hasMessages: boolean;
  sessions: SessionHistoryEntry[];
  activeSessionId: string;
  onSelectSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
  isExpanded: boolean;
  /** Mirrors the hook's skipAll preference. Renders an inline badge cue. */
  skipAll?: boolean;
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
  skipAll = false,
}: AssistantHeaderProps) {
  const { t } = useTranslation();
  const isAtSessionLimit = sessions.length >= ASSISTANT_MAX_SESSIONS;
  const isNewSessionDisabled = !hasMessages || isAtSessionLimit;

  return (
    <div className="flex h-12 items-center justify-between px-4">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-medium text-foreground">
          {t("assistant.title")}
        </h2>
        {skipAll && (
          <span
            data-testid="assistant-skip-all-badge"
            className="flex h-5 items-center gap-1 rounded-full border border-muted-foreground/30 bg-muted-foreground/10 px-2 text-[10px] font-medium uppercase tracking-wide text-muted-foreground"
            title="Skip-all mode is on. Plans, flow proposals, and validated components auto-approve. Type /skip-all to toggle off."
          >
            <ForwardedIconComponent name="Zap" className="h-2.5 w-2.5" />
            Skip-all
          </span>
        )}
      </div>
      <div className="flex items-center">
        <ShadTooltip
          content={
            isAtSessionLimit
              ? t("assistant.maxSessionsTooltip", {
                  max: ASSISTANT_MAX_SESSIONS,
                })
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
              {isAtSessionLimit
                ? t("assistant.maxSessionsLabel")
                : t("assistant.newSession")}
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
      </div>
    </div>
  );
}
