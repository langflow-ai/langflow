import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import type {
  TriggerRead,
  TriggerState,
} from "@/controllers/API/queries/triggers";
import { cn } from "@/utils/utils";
import {
  badgeLabelKey,
  badgeStateOf,
  TRIGGER_BADGE_STYLE,
} from "./helpers/trigger-presentation";

export interface TriggerStateBadgeProps {
  state: TriggerState;
  reason?: TriggerRead["reason"];
  className?: string;
}

/** The trigger's state as an icon plus text, never color alone. */
export function TriggerStateBadge({
  state,
  reason,
  className,
}: TriggerStateBadgeProps) {
  const { t } = useTranslation();
  const badgeState = badgeStateOf(state, reason);
  const style = TRIGGER_BADGE_STYLE[badgeState];
  return (
    <Badge
      variant="outline"
      size="xq"
      className={cn(
        "w-fit gap-1 whitespace-nowrap",
        style.className,
        className,
      )}
      data-testid="trigger-state-badge"
      data-state={state}
    >
      <ForwardedIconComponent
        name={style.icon}
        aria-hidden="true"
        className={cn(
          "h-3 w-3 shrink-0",
          badgeState === "pending" && "motion-safe:animate-spin",
        )}
      />
      {t(badgeLabelKey(badgeState))}
    </Badge>
  );
}

export default TriggerStateBadge;
