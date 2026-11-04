import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import {
  parseServerTime,
  sourceKeyOf,
} from "@/components/core/triggers/helpers/trigger-presentation";
import {
  type TriggerSessionRead,
  useTriggerSessionsQuery,
} from "@/controllers/API/queries/triggers";
import useFlowStore from "@/stores/flowStore";

const formatStartedAt = (time: number, locale: string): string =>
  new Intl.DateTimeFormat(locale, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  }).format(time);

/**
 * Readable labels for the Playground's trigger-run sessions: when each one
 * started and what started it, e.g. "Oct 29, 3:45:12 PM · Schedule". The time
 * leads because it is what tells runs apart, and the sidebar truncates the
 * end. The raw id stays the session's key, tooltip and header; a session
 * without a label shows its id.
 */
export function useSessionLabels(
  flowId: string | undefined,
  sessions: readonly string[],
): ReadonlyMap<string, string> {
  const { t, i18n } = useTranslation();
  // The shared Playground's visitors cannot read the flow's triggers.
  const isShareablePlayground = useFlowStore((state) => state.playgroundPage);
  const { data } = useTriggerSessionsQuery(
    flowId,
    sessions,
    !isShareablePlayground,
  );

  return useMemo(() => {
    const labelOf = (origin: TriggerSessionRead): string => {
      const source = t(sourceKeyOf(origin));
      // A shared session collects every run of its trigger.
      if (origin.session_id === `trigger:${origin.trigger_id}`) {
        return `${source} · ${t("chat.triggerSessionAllRuns")}`;
      }
      const startedAt = parseServerTime(origin.started_at);
      return startedAt === null
        ? source
        : `${formatStartedAt(startedAt, i18n.language)} · ${source}`;
    };
    return new Map(
      (data ?? []).map((origin) => [origin.session_id, labelOf(origin)]),
    );
  }, [data, t, i18n.language]);
}
