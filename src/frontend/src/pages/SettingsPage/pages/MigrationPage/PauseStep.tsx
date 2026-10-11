import { useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  type MigrationError,
  type MigrationJob,
  type MigrationState,
  type MigrationStepState,
  type MigrationWayBack,
  migrationKeys,
  runSourceChecks,
  useCancelJobMutation,
  usePauseMutation,
  useResumeMutation,
} from "@/controllers/API/queries/migration";
import ConfirmationModal from "@/modals/confirmationModal";
import { CHECK_TOTAL, formatTime, hasStarted, JOB_STATES } from "./catalog";

/** The body of "Pause changes": the pause, what it still waits for, and the check that has to pass again once it is on. */
export function PauseStep({
  migration,
  state,
}: {
  migration: MigrationState;
  state: MigrationStepState;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const pause = usePauseMutation();
  const [confirming, setConfirming] = useState(false);
  // The check this page runs once the pause is on: how many checks came back, and whether it could start.
  const [checked, setChecked] = useState<number>();
  const [refused, setRefused] = useState(false);

  // A check from before the pause says nothing about what the instance held when it stopped.
  const recheck = async () => {
    setRefused(false);
    setChecked(0);
    let started = false;
    const refusal = await runSourceChecks({
      targetVersion: migration.record.target.version ?? "",
      controller: new AbortController(),
      onEvent: (event) => {
        // The record says running once the stream starts, which the check's own step shows.
        if (!started) {
          started = true;
          queryClient.invalidateQueries({ queryKey: migrationKeys.all });
        }
        if (event.event === "check") setChecked((count = 0) => count + 1);
      },
    });
    await queryClient.invalidateQueries({ queryKey: migrationKeys.all });
    setChecked(undefined);
    // Another admin's run (409) counts as well, and shows once the record is read again.
    setRefused(Boolean(refusal) && refusal?.status !== 409);
  };
  const pauseNow = () => pause.mutate(undefined, { onSuccess: recheck });

  if (state.reason === "recheck_failed") {
    return (
      <p role="alert" className="text-sm text-destructive">
        {t("settings.migration.pause.recheckFailed", {
          step: t("settings.migration.step.check.title"),
        })}
      </p>
    );
  }
  if (state.reason === "recheck_pending") {
    const running =
      checked !== undefined ||
      migration.record.steps.check_source?.status === "running";
    return (
      <div aria-live="polite" className="flex flex-col items-start gap-3">
        {running ? (
          <p className="text-sm text-muted-foreground">
            {t("settings.migration.pause.rechecking")}
            {checked !== undefined &&
              ` ${t("settings.migration.check.running", { done: checked, total: CHECK_TOTAL })}`}
          </p>
        ) : (
          <>
            <p className="text-sm">
              {t("settings.migration.pause.recheckIdle")}
            </p>
            {refused && (
              <p className="text-sm text-destructive">
                {t("settings.migration.check.failed")}
              </p>
            )}
            <Button
              className="w-full sm:w-fit"
              onClick={recheck}
              ignoreTitleCase
            >
              {t("settings.migration.check.runAgain")}
            </Button>
          </>
        )}
      </div>
    );
  }

  const refusal = pause.error?.response?.data?.detail;
  // Either way the pause waits for something that has not ended, and the server says what.
  const waiting =
    refusal?.code === "jobs_active" || refusal?.code === "requests_active"
      ? refusal
      : undefined;
  return (
    <div className="flex flex-col items-start gap-4">
      <p className="text-sm text-muted-foreground">
        {t("settings.migration.pause.body")}
      </p>
      {waiting && <Waiting refusal={waiting} />}
      {pause.isError && !waiting && (
        <p role="alert" className="text-sm text-destructive">
          {t(
            refusal?.code === "pause_ended"
              ? "settings.migration.pause.ended"
              : "settings.migration.failed",
          )}
        </p>
      )}
      <Button
        className="w-full sm:w-fit"
        loading={pause.isPending}
        // Asked once: checking again is the same pause the admin already agreed to.
        onClick={() => (waiting ? pauseNow() : setConfirming(true))}
        ignoreTitleCase
      >
        {waiting
          ? t("settings.migration.pause.checkAgain")
          : t("settings.migration.pause.action")}
      </Button>
      <ConfirmationModal
        open={confirming}
        onClose={() => setConfirming(false)}
        onCancel={() => setConfirming(false)}
        title={t("settings.migration.pause.confirmTitle")}
        cancelText={t("modal.cancelButton")}
        confirmationText={t("settings.migration.pause.confirmAction")}
        onConfirm={() => {
          setConfirming(false);
          pauseNow();
        }}
        size="x-small"
      >
        <ConfirmationModal.Content>
          {t("settings.migration.pause.confirmBody")}
        </ConfirmationModal.Content>
      </ConfirmationModal>
    </div>
  );
}

/** What is still writing to this instance. The server lists it and stops none of it, so the admin decides. */
export function Waiting({ refusal }: { refusal: MigrationError }) {
  const { t, i18n } = useTranslation();
  const jobs = refusal.jobs ?? [];
  const listeners = refusal.listeners ?? [];
  const changes = refusal.changes ?? [];
  return (
    <div className="flex w-full flex-col gap-3">
      {jobs.length > 0 && (
        <>
          <p role="alert" className="text-sm">
            {t("settings.migration.pause.jobs", { count: jobs.length })}
          </p>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("settings.migration.pause.col.run")}</TableHead>
                  <TableHead>
                    {t("settings.migration.pause.col.owner")}
                  </TableHead>
                  <TableHead>
                    {t("settings.migration.pause.col.state")}
                  </TableHead>
                  <TableHead>
                    {t("settings.migration.pause.col.started")}
                  </TableHead>
                  <TableHead>
                    <span className="sr-only">
                      {t("settings.migration.pause.cancel")}
                    </span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((job) => (
                  <JobRow key={job.id} job={job} />
                ))}
              </TableBody>
            </Table>
          </div>
        </>
      )}
      {listeners.length > 0 && (
        <>
          <p role="alert" className="text-sm">
            {t("settings.migration.pause.listeners", {
              count: listeners.length,
            })}
          </p>
          <ul lang="en" className="font-mono text-xs text-muted-foreground">
            {listeners.map((listener) => (
              <li key={listener.holder}>{listener.holder}</li>
            ))}
          </ul>
        </>
      )}
      {changes.length > 0 && (
        <>
          <p role="alert" className="text-sm">
            {t("settings.migration.pause.changes", { count: changes.length })}
          </p>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>
                    {t("settings.migration.pause.col.what")}
                  </TableHead>
                  <TableHead>
                    {t("settings.migration.pause.col.started")}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {changes.map((change, index) => (
                  <TableRow
                    // The server gives a change no id, and two can be alike.
                    key={index}
                    data-testid={`migration-change-${index}`}
                  >
                    <TableCell>
                      {t(`settings.migration.pause.change.${change.kind}`)}{" "}
                      <span
                        // Each kind fills the parts it has: a request its method and path, a websocket its path, the rest a name.
                        lang="en"
                        className="font-mono text-xs text-muted-foreground"
                      >
                        {[change.method, change.path, change.name]
                          .filter(Boolean)
                          .join(" ")}
                      </span>
                    </TableCell>
                    <TableCell>
                      {formatTime(change.since, i18n.language)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </>
      )}
      {refusal.elsewhere && (
        <p role="alert" className="text-sm">
          {t("settings.migration.pause.elsewhere")}
        </p>
      )}
      {refusal.code === "requests_active" &&
        changes.length === 0 &&
        !refusal.elsewhere && (
          // Whatever held the pause back ended as the server answered, so it has nothing to name.
          <p role="alert" className="text-sm">
            {t("settings.migration.pause.requestsActive")}
          </p>
        )}
    </div>
  );
}

function JobRow({ job }: { job: MigrationJob }) {
  const { t, i18n } = useTranslation();
  const cancel = useCancelJobMutation();
  const name = job.flow_name ?? job.knowledge_base ?? job.id;
  const state = JOB_STATES[job.state];
  const request = job.cancel;
  return (
    <TableRow data-testid={`migration-job-${job.id}`}>
      <TableCell>{name}</TableCell>
      <TableCell>{job.owner}</TableCell>
      <TableCell>
        {state ? (
          t(`settings.migration.job.${state}`)
        ) : (
          <span lang="en">{job.state}</span>
        )}
        {job.state === "suspended" && (
          <p className="text-xs text-muted-foreground">
            {t("settings.migration.pause.waitingNote")}
          </p>
        )}
      </TableCell>
      <TableCell>{formatTime(job.started_at, i18n.language)}</TableCell>
      <TableCell>
        {cancel.isSuccess ? (
          t("settings.migration.pause.cancelled")
        ) : request ? (
          <Button
            variant="outline"
            size="sm"
            loading={cancel.isPending}
            onClick={() => cancel.mutate(request)}
            // Every row has this button, so its name says which run it cancels.
            aria-label={`${t("settings.migration.pause.cancel")}, ${name}`}
            ignoreTitleCase
          >
            {t("settings.migration.pause.cancel")}
          </Button>
        ) : (
          t("settings.migration.pause.noCancel")
        )}
        {cancel.isError && (
          <p role="alert" className="text-xs text-destructive">
            {t("settings.migration.pause.cancelFailed")}
          </p>
        )}
      </TableCell>
    </TableRow>
  );
}

/** Stays in view while changes are paused, wherever the admin is on the page. */
export function PausedBanner({ migration }: { migration: MigrationState }) {
  const { t, i18n } = useTranslation();
  // A pause that still waits refuses changes as well, and one that the server left behind stays. It is
  // no pause yet for the backup or a copy, so the banner does not call it one.
  const { pause, pausing } = migration.record;
  const refused = pause ?? pausing;
  return (
    // Stays in the accessibility tree while empty, so the pause is announced when it starts.
    <div role="status" className="sticky top-0 z-10 empty:-mt-6">
      {refused && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-accent-amber-foreground bg-accent-amber px-4 py-3 text-sm">
          <p className="min-w-48 flex-1">
            <span className="font-medium">
              {t(
                pause
                  ? "settings.migration.pause.banner"
                  : "settings.migration.pause.bannerWaiting",
              )}
            </span>{" "}
            {t(
              pause
                ? "settings.migration.pause.done"
                : "settings.migration.pause.asked",
              {
                time: formatTime(refused.frozen_at, i18n.language),
                user: refused.frozen_by,
              },
            )}
          </p>
          {/* Once the new instance has started, going back takes more than a click: see "If something goes wrong". */}
          {!hasStarted(migration) && <ResumeButton />}
        </div>
      )}
    </div>
  );
}

/** "If something goes wrong": the way back from where the move stands now. */
export function Recovery({ migration }: { migration: MigrationState }) {
  const { t } = useTranslation();
  const refused = migration.record.pause ?? migration.record.pausing;
  const started = Boolean(refused) && hasStarted(migration);
  return (
    // Once the new instance has started, this is where the admin has to look, so it opens by itself.
    <details className="rounded-lg border p-4" open={started || undefined}>
      <summary className="cursor-pointer text-sm font-medium">
        {t("settings.migration.recovery.title")}
      </summary>
      {started ? (
        // The admin's word is about one start. After a way back and another start it is asked again.
        <WayBack
          key={migration.record.steps.start_target?.confirmed_at}
          migration={migration}
        />
      ) : (
        <div className="flex flex-col items-start gap-3 pt-3">
          <p className="text-sm text-muted-foreground">
            {refused
              ? t("settings.migration.recovery.paused")
              : t("settings.migration.recovery.none")}
          </p>
          {refused && <ResumeButton />}
        </div>
      )}
    </details>
  );
}

/** What going back takes once the new instance has started, and the admin's word that it is done. */
function WayBack({ migration }: { migration: MigrationState }) {
  const { t } = useTranslation();
  // An instance on PostgreSQL shares its database with the new instance, which has updated it.
  const shared = migration.instance.database.type === "postgresql";
  const id = useId();
  const [stopped, setStopped] = useState(false);
  const [restored, setRestored] = useState(false);
  return (
    <div className="flex flex-col items-start gap-3 pt-3">
      <p id={`${id}-warning`} className="text-sm text-destructive">
        {t("settings.migration.recovery.started")}
      </p>
      <ol className="list-decimal pl-5 text-sm text-muted-foreground">
        <li>{t("settings.migration.recovery.stopTarget")}</li>
        <li>
          {shared
            ? t("settings.migration.recovery.restore", {
                location: migration.record.backup?.location ?? "",
              })
            : t("settings.migration.recovery.sqliteNote")}
        </li>
      </ol>
      <div className="flex items-center gap-2">
        <Checkbox
          id={`${id}-stopped`}
          checked={stopped}
          onCheckedChange={(value) => setStopped(value === true)}
        />
        <Label htmlFor={`${id}-stopped`} className="text-sm font-normal">
          {t("settings.migration.recovery.ackStopped")}
        </Label>
      </div>
      {shared && (
        <div className="flex items-center gap-2">
          <Checkbox
            id={`${id}-restored`}
            checked={restored}
            onCheckedChange={(value) => setRestored(value === true)}
          />
          <Label htmlFor={`${id}-restored`} className="text-sm font-normal">
            {t("settings.migration.recovery.ackRestored")}
          </Label>
        </div>
      )}
      <ResumeButton
        back={{
          target_stopped: true,
          ...(shared && { database_restored: true }),
        }}
        ready={stopped && (!shared || restored)}
        waitsFor={`${id}-warning`}
        // The destination keeps the copy and what the new instance wrote, and a copy needs an empty database.
        // Where the database is shared, the restore put it back as it was.
        again={shared ? undefined : t("settings.migration.resume.newDatabase")}
      />
    </div>
  );
}

/**
 * Turns changes back on, after a second word. `back` is the admin's word about the new instance once it has
 * started. `ready` is false until they gave it, and `waitsFor` names the text that says what it waits for.
 */
function ResumeButton({
  back,
  ready = true,
  waitsFor,
  again,
}: {
  back?: MigrationWayBack;
  ready?: boolean;
  waitsFor?: string;
  /** What the next move takes, said before the admin gives this one up. */
  again?: string;
}) {
  const { t } = useTranslation();
  const resume = useResumeMutation();
  const [confirming, setConfirming] = useState(false);
  return (
    <>
      <Button
        variant="outline"
        size="sm"
        loading={resume.isPending}
        disabled={!ready}
        aria-describedby={ready ? undefined : waitsFor}
        onClick={() => setConfirming(true)}
        ignoreTitleCase
      >
        {t("settings.migration.pause.resume")}
      </Button>
      {resume.isError && (
        <p role="alert" className="text-sm text-destructive">
          {t("settings.migration.failed")}
        </p>
      )}
      <ConfirmationModal
        open={confirming}
        onClose={() => setConfirming(false)}
        onCancel={() => setConfirming(false)}
        title={t("settings.migration.resume.confirmTitle")}
        cancelText={t("modal.cancelButton")}
        confirmationText={t("settings.migration.resume.confirmAction")}
        onConfirm={() => {
          setConfirming(false);
          resume.mutate(back);
        }}
        size="x-small"
      >
        <ConfirmationModal.Content>
          {t(
            back
              ? "settings.migration.resume.confirmBodyStarted"
              : "settings.migration.resume.confirmBody",
          )}
          {again && ` ${again}`}
        </ConfirmationModal.Content>
      </ConfirmationModal>
    </>
  );
}
