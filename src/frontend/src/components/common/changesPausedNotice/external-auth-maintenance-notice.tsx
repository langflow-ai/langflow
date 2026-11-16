import { useTranslation } from "react-i18next";

export function ExternalAuthMaintenanceNotice() {
  const { t } = useTranslation();

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <section aria-label={t("settings.maintenance.statusLabel")}>
        <p
          role="status"
          className="max-w-xl rounded-lg border border-accent-amber-foreground bg-accent-amber p-4 text-sm"
        >
          {t("settings.maintenance.externalAuthNotice")}
        </p>
      </section>
    </main>
  );
}
