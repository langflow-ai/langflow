import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import {
  ASSISTANT_MAX_SESSIONS,
  ASSISTANT_TITLE,
} from "../assistant-panel.constants";
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
}: AssistantHeaderProps) {
  const { t } = useTranslation();
  const isAtSessionLimit = sessions.length >= ASSISTANT_MAX_SESSIONS;
  const isNewSessionDisabled = !hasMessages || isAtSessionLimit;

  return (
    <div className="flex h-12 items-center justify-between px-4">
      <h2 className="text-sm font-medium text-foreground">{ASSISTANT_TITLE}</h2>
      <div className="flex items-center">
        <ShadTooltip
          content={
            isAtSessionLimit
              ? t("assistant.maxSessionsTooltip", { max: ASSISTANT_MAX_SESSIONS })
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
              {isAtSessionLimit ? t("assistant.maxSessionsLabel") : t("assistant.newSession")}
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
