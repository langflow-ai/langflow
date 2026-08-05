import { useTranslation } from "react-i18next";

// Screen-reader-only companion to useResponseCompleteCue.
export function ResponseCompleteStatus({
  completedCount,
}: {
  completedCount: number;
}) {
  const { t } = useTranslation();
  // A single persistent text node that mutates in place is the announcement
  // pattern WebKit's live-region diffing handles reliably; remounting a keyed
  // child (remove + re-add of identical text) is dropped by Safari/VoiceOver
  // (LE-2041 QA). Alternate a trailing no-break space so consecutive
  // completions still produce a text change to announce.
  const message =
    completedCount > 0
      ? t("chat.responseComplete") + (completedCount % 2 === 0 ? "\u00a0" : "")
      : "";
  return (
    <div role="status" aria-live="polite" className="sr-only">
      {message}
    </div>
  );
}
