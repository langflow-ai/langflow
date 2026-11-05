import { useTranslation } from "react-i18next";
import { useLocation } from "react-router-dom";
import { useMigrationPauseQuery } from "@/controllers/API/queries/migration";

/** Tells every signed-in user, on every page, that this instance refuses changes while it moves to a new one. */
export function ChangesPausedNotice() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const { data } = useMigrationPauseQuery();
  // Its own banner covers the file pause, while database maintenance needs this notice too.
  const showNotice =
    data?.paused &&
    (data.maintenance || !pathname.includes("/settings/migration"));
  const messageKey = data?.migration
    ? "settings.migration.pause.notice"
    : data?.externalAuthenticationPaused
      ? "settings.maintenance.externalAuthNotice"
      : data?.maintenance
        ? "settings.maintenance.notice"
        : "settings.migration.pause.notice";
  return (
    <section
      aria-label={t("settings.maintenance.statusLabel")}
      className="pointer-events-none fixed bottom-4 left-1/2 z-50 w-max max-w-[min(36rem,calc(100%-2rem))] -translate-x-1/2"
    >
      {/* Keep the empty status mounted so screen readers announce later changes. */}
      <div role="status" data-testid="changes-paused-notice">
        {showNotice && (
          <p className="rounded-lg border border-accent-amber-foreground bg-accent-amber px-4 py-2 text-sm shadow-lg">
            {t(messageKey)}
          </p>
        )}
      </div>
    </section>
  );
}
