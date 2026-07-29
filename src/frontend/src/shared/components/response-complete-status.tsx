import { useTranslation } from "react-i18next";

// Screen-reader-only companion to useResponseCompleteCue.
export function ResponseCompleteStatus({
  completedCount,
}: {
  completedCount: number;
}) {
  const { t } = useTranslation();
  return (
    <div role="status" aria-live="polite" className="sr-only">
      {completedCount > 0 && (
        // Keyed so an identical announcement still replaces the region's
        // content and gets re-announced on every completed response.
        <span key={completedCount}>{t("chat.responseComplete")}</span>
      )}
    </div>
  );
}
