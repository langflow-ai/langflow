import { useTranslation } from "react-i18next";
import type { TriggerRead } from "@/controllers/API/queries/triggers";
import {
  formatDateTime,
  formatRelativeTime,
} from "./helpers/format-relative-time";
import { parseServerTime, transportOf } from "./helpers/trigger-presentation";

/**
 * How events arrive (B6): push, socket, poll or a signed request. A schedule
 * names its next run instead, which is what an owner wants to know.
 */
export function TriggerTransportLabel({
  trigger,
}: {
  trigger: Pick<TriggerRead, "kind" | "config" | "next_fire_at">;
}) {
  const { t, i18n } = useTranslation();
  const transport = transportOf(trigger);
  if (transport !== "schedule")
    return <>{t(`triggers.transport.${transport}`)}</>;
  const next = parseServerTime(trigger.next_fire_at);
  if (next === null) return <>{t("triggers.schedule.notScheduled")}</>;
  return (
    <time
      dateTime={new Date(next).toISOString()}
      title={formatDateTime(next, i18n.language)}
    >
      {t("triggers.schedule.next", {
        time: formatRelativeTime(next, i18n.language),
      })}
    </time>
  );
}

export default TriggerTransportLabel;
