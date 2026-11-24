import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  type MigrationState,
  useConfirmStartMutation,
} from "@/controllers/API/queries/migration";
import ConfirmationModal from "@/modals/confirmationModal";
import { Details } from "./CheckStep";
import { formatTime } from "./catalog";

/**
 * The body of "Start the new instance". The admin starts it themselves, somewhere this page can't reach,
 * so the step says that this is one-way, shows the settings to start it with and what to try on it, and takes
 * the admin's word that it runs. That word ends the move.
 */
export function StartStep({ migration }: { migration: MigrationState }) {
  const { t, i18n } = useTranslation();
  const confirm = useConfirmStartMutation();
  const [asking, setAsking] = useState(false);
  // Until the admin has agreed that the move is one-way, nothing here tells them how to start the new instance.
  const [agreed, setAgreed] = useState(false);
  const { instance, record } = migration;
  const settings = migration.start?.settings ?? [];
  // "Show the settings" is gone once the admin agreed. Focus goes to what took its place.
  const intro = useRef<HTMLParagraphElement>(null);
  useEffect(() => {
    if (agreed) intro.current?.focus();
  }, [agreed]);
  // What the first step said about roles. It names this step as the place to deal with it.
  const roles = record.steps.check_source?.report?.checks.find(
    (check) => check.name === "role assignments" && check.status === "warn",
  );
  if (!agreed) {
    // What the steps before this one left behind. The server holds this step back until each is true.
    const facts = [
      record.backup?.location &&
        t("settings.migration.gate.factBackup", {
          location: record.backup.location,
        }),
      record.pause &&
        t("settings.migration.gate.factPaused", {
          time: formatTime(record.pause.frozen_at, i18n.language),
        }),
      t("settings.migration.gate.factKey"),
      t("settings.migration.gate.factCopies"),
      t("settings.migration.gate.factChecked"),
    ].filter(Boolean);
    return (
      <div className="flex flex-col items-start gap-4">
        <p className="text-sm text-muted-foreground">
          {t("settings.migration.start.body")}
        </p>
        <Button
          className="w-full sm:w-fit"
          onClick={() => setAsking(true)}
          ignoreTitleCase
        >
          {t("settings.migration.start.showSettings")}
        </Button>
        <ConfirmationModal
          open={asking}
          onClose={() => setAsking(false)}
          onCancel={() => setAsking(false)}
          title={t("settings.migration.gate.title")}
          cancelText={t("modal.cancelButton")}
          confirmationText={t("settings.migration.gate.action")}
          destructive
          onConfirm={() => {
            setAsking(false);
            setAgreed(true);
          }}
          size="x-small"
        >
          <ConfirmationModal.Content>
            <div className="flex flex-col gap-3">
              <p>
                {t(
                  instance.database.type === "sqlite"
                    ? "settings.migration.gate.bodySqlite"
                    : "settings.migration.gate.bodyPostgres",
                )}
              </p>
              <ul className="list-disc pl-5 text-sm text-muted-foreground">
                {facts.map((fact) => (
                  <li key={String(fact)}>{fact}</li>
                ))}
              </ul>
            </div>
          </ConfirmationModal.Content>
        </ConfirmationModal>
      </div>
    );
  }

  // With nothing to start the new instance with, the step must not take the admin's word that it runs.
  if (settings.length === 0)
    return (
      <p
        ref={intro}
        tabIndex={-1}
        role="alert"
        className="text-sm text-destructive"
      >
        {t("settings.migration.failed")}
      </p>
    );

  return (
    <div className="flex flex-col items-start gap-4">
      <div className="flex w-full flex-col gap-2">
        <p ref={intro} tabIndex={-1} className="text-sm">
          {t("settings.migration.start.settingsIntro")}
        </p>
        <pre
          lang="en"
          className="select-all whitespace-pre-wrap break-words rounded-md bg-muted p-2 font-mono text-xs"
          data-testid="migration-start-settings"
        >
          {settings
            .map((setting) => `${setting.name}=${setting.value}`)
            .join("\n")}
        </pre>
        <p className="text-xs text-muted-foreground">
          {t("settings.migration.start.fillHint")}
        </p>
        <p className="text-xs text-muted-foreground">
          {t("settings.migration.start.foldersNote")}
        </p>
        {/* Two things the list can't print, since the record keeps neither. Without them the new instance can
            read another schema, or fail to reach the bucket, and nothing on this page would notice the first. */}
        {settings.some((setting) => setting.value.includes("://<user>")) && (
          <p className="text-xs text-muted-foreground">
            {t("settings.migration.start.optionsNote")}
          </p>
        )}
        {settings.some((setting) => setting.name === "AWS_ACCESS_KEY_ID") && (
          <p className="text-xs text-muted-foreground">
            {t("settings.migration.start.caNote")}
          </p>
        )}
      </div>
      {roles && (
        <div className="flex w-full flex-col gap-1 text-sm">
          <span className="font-medium">
            {t("settings.migration.check.roleAssignments.title")}
          </span>
          <p className="text-muted-foreground">
            {t("settings.migration.check.roleAssignments.body")}
          </p>
          <Details text={roles.summary} open />
        </div>
      )}
      {/* The copy was checked from this server. Whether the new instance works on it is for the admin to see. */}
      <div className="flex flex-col gap-1 text-sm">
        <span className="font-medium">
          {t("settings.migration.tryIt.title")}
        </span>
        <ul className="list-disc pl-5 text-muted-foreground">
          {["signIn", "credential", "file", "kb"].map((item) => (
            <li key={item}>{t(`settings.migration.tryIt.${item}`)}</li>
          ))}
        </ul>
      </div>
      {confirm.isError && (
        <p role="alert" className="text-sm text-destructive">
          {t("settings.migration.failed")}
        </p>
      )}
      <Button
        className="w-full sm:w-fit"
        loading={confirm.isPending}
        onClick={() => confirm.mutate()}
        ignoreTitleCase
      >
        {t("settings.migration.start.action")}
      </Button>
    </div>
  );
}

/** What the page says once the new instance runs and the move is over: what to keep, and what to do with this instance. */
export function MoveComplete({ migration }: { migration: MigrationState }) {
  const { t } = useTranslation();
  const done = migration.steps.some(
    (step) => step.id === "start_target" && step.state === "done",
  );
  // The button that ended the move is gone with it, and focus fell on <body>. It goes to what took the
  // button's place, which also reads it out. A page opened on a finished move leaves focus where it is, and so
  // does one where the admin is busy elsewhere while another tab ends the move.
  const panel = useRef<HTMLDivElement>(null);
  const wasDone = useRef(done);
  useEffect(() => {
    if (done && !wasDone.current && document.activeElement === document.body)
      panel.current?.focus();
    wasDone.current = done;
  }, [done]);
  if (!done) return null;
  return (
    <div
      ref={panel}
      tabIndex={-1}
      className="flex flex-col gap-1 rounded-md border bg-muted/40 p-3 text-sm"
      data-testid="migration-complete"
    >
      <p>{t("settings.migration.complete.body")}</p>
      {migration.instance.database.type === "postgresql" && (
        <p className="font-medium">
          {t("settings.migration.complete.postgres")}
        </p>
      )}
    </div>
  );
}
