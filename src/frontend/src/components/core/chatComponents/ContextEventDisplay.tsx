import { useTranslation } from "react-i18next";
import { formatSeconds } from "@/components/core/playgroundComponent/chat-view/chat-messages/utils/format";
import type { ContextContent } from "@/types/chat";
import ForwardedIconComponent from "../../common/genericIconComponent";

/**
 * One muted line that says the Agent summarized older messages (a fold) or
 * compacted the context of the run. The backend updates the same block from
 * "running" to "done" or "failed" while the message streams.
 */
export function ContextEventDisplay({ content }: { content: ContextContent }) {
  const { t, i18n } = useTranslation();
  const running = content.state === "running";
  const tokens = (value?: number | null) =>
    new Intl.NumberFormat(i18n.language).format(value ?? 0);

  let label: string;
  if (content.kind === "fold") {
    const count = content.messages ?? 0;
    label =
      content.state === "failed"
        ? t("chat.contextEvent.foldFailed")
        : t(
            running
              ? "chat.contextEvent.foldRunning"
              : "chat.contextEvent.foldDone",
            { count },
          );
  } else if (content.state === "done") {
    label = t("chat.contextEvent.compactionDone", {
      before: tokens(content.tokens_before),
      after: tokens(content.tokens_after),
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
      data-testid={`context-event-${content.kind}-${content.state}`}
      className="flex items-center gap-1.5 text-xs text-muted-foreground"
    >
      <ForwardedIconComponent
        name={content.kind === "fold" ? "History" : "Shrink"}
        className="h-3 w-3"
        aria-hidden
      />
      <span className={running ? "animate-pulse" : undefined}>{label}</span>
      {!running && content.duration != null && (
        <span aria-hidden>· {formatSeconds(content.duration)}</span>
      )}
    </div>
  );
}
