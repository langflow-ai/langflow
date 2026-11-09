import { useTranslation } from "react-i18next";
import {
  formatDateTime,
  formatRelativeTime,
} from "@/components/core/triggers/helpers/format-relative-time";
import { parseServerTime } from "@/components/core/triggers/helpers/trigger-presentation";
import type { TriggerRead } from "@/controllers/API/queries/triggers";

/** When the trigger last fired, relative, with the exact time on hover. */
export function TriggerLastEventCell({ trigger }: { trigger: TriggerRead }) {
  const { t, i18n } = useTranslation();
  const time = parseServerTime(trigger.last_fired_at);
  if (time === null) {
    return (
      <span className="text-muted-foreground">
        {t("triggers.lastEvent.never")}
      </span>
    );
  }
  return (
    <time
      dateTime={new Date(time).toISOString()}
      title={formatDateTime(time, i18n.language)}
    >
      {formatRelativeTime(time, i18n.language)}
    </time>
  );
}

export default TriggerLastEventCell;
