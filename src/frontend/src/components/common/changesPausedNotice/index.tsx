import { useTranslation } from "react-i18next";
import { useLocation } from "react-router-dom";
import { useMigrationPauseQuery } from "@/controllers/API/queries/migration";
import { CustomLink } from "@/customization/components/custom-link";
import useAuthStore from "@/stores/authStore";
import { cn } from "@/utils/utils";

const MESSAGES = {
  migration: "settings.migration.pause.notice",
  externalAuth: "settings.maintenance.externalAuthNotice",
  maintenance: "settings.maintenance.notice",
};

/** Tells every signed-in user, on every page, that this instance refuses changes while it moves to a new one. */
export function ChangesPausedNotice({
  aboveComposer = false,
}: {
  aboveComposer?: boolean;
} = {}) {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const { data, isError } = useMigrationPauseQuery();
  const isAdmin = useAuthStore((state) => state.userData?.is_superuser);
  // Its own banner covers the file pause, while database maintenance needs this notice too.
  const showNotice =
    data?.paused &&
    (data.maintenance || !pathname.includes("/settings/migration"));
  const kind = data?.migration
    ? "migration"
    : data?.externalAuthenticationPaused
      ? "externalAuth"
      : data?.maintenance
        ? "maintenance"
        : "migration";
  // A failed refresh keeps the last answer, which may no longer be true.
  const messageKey =
    isError && kind !== "migration"
      ? "settings.maintenance.lastKnown"
      : MESSAGES[kind];
  const showManage =
    isAdmin &&
    kind === "maintenance" &&
    !pathname.includes("/settings/upgrade-reports");
  return (
    <section
      aria-label={t("settings.maintenance.statusLabel")}
      className={cn(
        "pointer-events-none fixed left-1/2 z-50 w-max max-w-[min(36rem,calc(100%-2rem))] -translate-x-1/2",
        aboveComposer
          ? "top-[calc(theme(spacing.16)+env(safe-area-inset-top))]"
          : "bottom-[calc(theme(spacing.4)+env(safe-area-inset-bottom))]",
      )}
    >
      {/* Keep the empty status mounted so screen readers announce later changes. */}
      <div role="status" data-testid="changes-paused-notice">
        {showNotice && (
          <p className="rounded-lg border border-accent-amber-foreground bg-accent-amber px-4 py-2 text-sm shadow-lg">
            {t(messageKey)}
            {showManage && (
              <>
                {" "}
                <CustomLink
                  to="/settings/upgrade-reports#upgrade-maintenance"
                  className="pointer-events-auto font-medium underline"
                >
                  {t("settings.upgrade.maintenance.manage")}
                </CustomLink>
              </>
            )}
          </p>
        )}
      </div>
    </section>
  );
}
