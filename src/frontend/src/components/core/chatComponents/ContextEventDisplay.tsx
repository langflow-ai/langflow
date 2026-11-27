import { useTranslation } from "react-i18next";
import { formatSeconds } from "@/components/core/playgroundComponent/chat-view/chat-messages/utils/format";
import type { ContextEvent } from "@/types/chat";
import ForwardedIconComponent from "../../common/genericIconComponent";

/**
 * One muted line that says the Agent summarized older messages (a fold) or
 * compacted the context of the run. The backend updates the same event from
 * "running" to "done" or "failed" while the message streams.
 */
export function ContextEventDisplay({ event }: { event: ContextEvent }) {
  const { t, i18n } = useTranslation();
  const running = event.state === "running";
  const tokens = (value?: number | null) =>
    new Intl.NumberFormat(i18n.language).format(value ?? 0);

  let label: string;
  if (event.kind === "fold") {
    const count = event.messages ?? 0;
    label =
      event.state === "failed"
        ? t("chat.contextEvent.foldFailed")
        : t(
            running
              ? "chat.contextEvent.foldRunning"
              : "chat.contextEvent.foldDone",
            { count },
          );
  } else if (event.state === "done") {
    label = t("chat.contextEvent.compactionDone", {
      before: tokens(event.tokens_before),
      after: tokens(event.tokens_after),
    });
  } else {
    label = t(
      running
        ? "chat.contextEvent.compactionRunning"
        : "chat.contextEvent.compactionFailed",
    );
  }

  return (
    <div
      data-testid={`context-event-${event.kind}-${event.state}`}
      className="flex items-center gap-1.5 text-xs text-muted-foreground"
    >
      <ForwardedIconComponent
        name={event.kind === "fold" ? "History" : "Shrink"}
        className="h-3 w-3"
        aria-hidden
      />
      <span className={running ? "animate-pulse" : undefined}>{label}</span>
      {!running && event.duration != null && (
        <span aria-hidden>· {formatSeconds(event.duration)}</span>
      )}
    </div>
  );
}
