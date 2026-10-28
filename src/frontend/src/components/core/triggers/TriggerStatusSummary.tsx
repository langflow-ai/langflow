import { useTranslation } from "react-i18next";
import type { TriggerRead } from "@/controllers/API/queries/triggers";
import { inlineFixOf, reasonKey } from "./helpers/trigger-presentation";
import TriggerStateBadge from "./TriggerStateBadge";

export interface TriggerStatusSummaryProps {
  trigger: TriggerRead;
  /** Runs the inline fix the server allows: reconnect or resume. */
  onFix?: (trigger: TriggerRead, action: "reconnect" | "resume") => void;
  busy?: boolean;
  /** Also explain a trigger that is running cleanly (no reason code). */
  explainRunning?: boolean;
}

/**
 * Badge, the one fix inline, the state reason, and the last error underneath.
 * The table row and the node popover render the same summary.
 */
export function TriggerStatusSummary({
  trigger,
  onFix,
  busy,
  explainRunning = false,
}: TriggerStatusSummaryProps) {
  const { t } = useTranslation();
  const fix = onFix ? inlineFixOf(trigger) : null;
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-2">
        <TriggerStateBadge state={trigger.state} reason={trigger.reason} />
        {fix && (
          <button
            type="button"
            disabled={busy}
            className="text-xs font-medium underline underline-offset-2 hover:text-primary disabled:opacity-50"
            onClick={() => onFix?.(trigger, fix)}
            aria-label={t(`triggers.fixAria.${fix}`, { name: trigger.name })}
            data-testid={`trigger-fix-${fix}`}
          >
            {t(`triggers.actions.${fix}`)}
          </button>
        )}
      </div>
      {(trigger.reason || explainRunning) && (
        <span className="max-w-[16rem] text-xs text-muted-foreground">
          {t(reasonKey(trigger))}
        </span>
      )}
      {trigger.last_error && (
        <span
          className="line-clamp-2 max-w-[16rem] break-words text-xs text-muted-foreground"
          title={trigger.last_error}
          data-testid="trigger-last-error"
        >
          {trigger.last_error}
        </span>
      )}
    </div>
  );
}

export default TriggerStatusSummary;
