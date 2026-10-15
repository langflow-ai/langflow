import { useTranslation } from "react-i18next";
import { useMigrationPauseQuery } from "@/controllers/API/queries/migration";
import { useUtilityStore } from "@/stores/utilityStore";

/** Tells every signed-in user, on every page, that this instance refuses changes while it moves to a new one. */
export function ChangesPausedNotice() {
  const { t } = useTranslation();
  const migrationOn = useUtilityStore(
    (state) => state.featureFlags.instance_migration === true,
  );
  const { data } = useMigrationPauseQuery(migrationOn);
  if (!migrationOn) return null;
  return (
    // Stays in the accessibility tree while empty, so the pause is announced when it starts.
    <div
      role="status"
      className="pointer-events-none fixed bottom-4 left-1/2 z-50 w-max max-w-[calc(100%-2rem)] -translate-x-1/2"
    >
      {data?.paused && (
        <p className="rounded-lg border border-accent-amber-foreground bg-accent-amber px-4 py-2 text-sm shadow-lg">
          {t("settings.migration.pause.notice")}
        </p>
      )}
    </div>
  );
}
