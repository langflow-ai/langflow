import type { AxiosResponse } from "axios";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  type MigrationState,
  useConfirmBackupMutation,
  useDownloadDatabaseMutation,
} from "@/controllers/API/queries/migration";
import { parseContentDispositionFilename } from "@/utils/parse-content-disposition-filename";
import { formatTime, pgDumpCommand } from "./catalog";

const FIELD = "migration-backup-location";

/** The body of "Back up this instance": a copy of the database, the folders to copy by hand, and where the admin keeps it all. */
export function BackupStep({ migration }: { migration: MigrationState }) {
  const { t, i18n } = useTranslation();
  const download = useDownloadDatabaseMutation();
  const confirm = useConfirmBackupMutation();
  const { instance, record } = migration;
  const sqlite = instance.database.type === "sqlite";
  // A copy from before this pause misses what changed after it was made.
  const downloadedAt = record.backup?.database_downloaded_at;
  const downloaded = Boolean(
    downloadedAt &&
      record.pause &&
      new Date(downloadedAt) > new Date(record.pause.frozen_at),
  );
  const missing = sqlite && !downloaded;
  // The server holds the same rule, and says so when this page was out of date.
  const refused =
    confirm.error?.response?.data?.detail?.code === "database_not_downloaded";
  const folders = [
    instance.knowledge_bases.local &&
      instance.knowledge_bases.folder &&
      t("settings.migration.backup.kbFolder", {
        path: instance.knowledge_bases.folder,
      }),
    instance.files.local &&
      instance.files.folder &&
      t("settings.migration.backup.filesFolder", {
        path: instance.files.folder,
      }),
  ].filter(Boolean);

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        const location = new FormData(event.currentTarget).get("location");
        confirm.mutate(String(location));
      }}
    >
      <p className="text-sm text-muted-foreground">
        {t("settings.migration.backup.body")}
      </p>
      {sqlite ? (
        <div className="flex flex-col items-start gap-2">
          <Button
            type="button"
            variant="outline"
            className="w-full sm:w-fit"
            loading={download.isPending}
            onClick={() => download.mutate(undefined, { onSuccess: save })}
            ignoreTitleCase
          >
            {t("settings.migration.backup.downloadDb")}
          </Button>
          <p className="text-xs text-muted-foreground">
            {t("settings.migration.backup.dbNote")}
          </p>
          <p role="status" className="text-sm empty:hidden">
            {downloaded &&
              t("settings.migration.backup.dbDownloaded", {
                time: formatTime(downloadedAt, i18n.language),
              })}
          </p>
          {download.isError && (
            <p role="alert" className="text-sm text-destructive">
              {t("settings.migration.backup.failed")}
            </p>
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <p className="text-sm">{t("settings.migration.backup.pgIntro")}</p>
          <pre
            lang="en"
            className="select-all whitespace-pre-wrap break-words rounded-md bg-muted p-2 font-mono text-xs"
          >
            {pgDumpCommand(instance.database.location ?? "")}
          </pre>
        </div>
      )}
      {folders.length > 0 && (
        <div className="flex flex-col gap-1">
          <ul className="break-words text-sm">
            {folders.map((folder) => (
              <li key={folder}>{folder}</li>
            ))}
          </ul>
          <p className="text-xs text-muted-foreground">
            {t("settings.migration.backup.folderHint")}
          </p>
        </div>
      )}
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={FIELD}>
          {t("settings.migration.backup.location.label")}
        </Label>
        <Input
          id={FIELD}
          name="location"
          defaultValue={record.backup?.location}
          spellCheck={false}
          required
          aria-describedby={`${FIELD}-help`}
        />
        <p id={`${FIELD}-help`} className="text-xs text-muted-foreground">
          {t("settings.migration.backup.location.help")}
        </p>
      </div>
      {confirm.isError && (
        <p role="alert" className="text-sm text-destructive">
          {refused
            ? t("settings.migration.backup.downloadFirst")
            : t("settings.migration.failed")}
        </p>
      )}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <Button
          type="submit"
          className="w-full sm:w-fit"
          disabled={missing}
          loading={confirm.isPending}
          aria-describedby={missing ? `${FIELD}-first` : undefined}
          ignoreTitleCase
        >
          {t("settings.migration.backup.action")}
        </Button>
        {missing && (
          <p id={`${FIELD}-first`} className="text-xs text-muted-foreground">
            {t("settings.migration.backup.downloadFirst")}
          </p>
        )}
      </div>
    </form>
  );
}

/** Hands the browser the copy the server sent, under the name the server gave it. */
function save(response: AxiosResponse<Blob>) {
  // ponytail: the whole copy sits in the browser's memory first. Stream it to disk if databases outgrow that.
  const link = document.createElement("a");
  link.href = URL.createObjectURL(response.data);
  link.download = parseContentDispositionFilename(
    response.headers["content-disposition"] ?? null,
    "langflow-backup.db",
  );
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
}
