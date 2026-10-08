import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  type CopyEvent,
  type CopyStepId,
  followCopy,
  type MigrationCopyRun,
  type MigrationState,
  type MigrationStepState,
  migrationKeys,
  useStartCopyMutation,
  useStopCopyMutation,
} from "@/controllers/API/queries/migration";
import ConfirmationModal from "@/modals/confirmationModal";
import { Details } from "./CheckStep";
import { COPIES, COPY_CODES, copyProgress, STEP_SLUGS } from "./catalog";

// How long the page waits before it asks again for a run whose connection dropped.
const RETRY_MS = 2000;

/** The body of a copy step: start the copy, follow it while it runs, stop it, and say how the last one went. */
export function CopyStep({
  migration,
  state,
  step,
}: {
  migration: MigrationState;
  state: MigrationStepState;
  step: CopyStepId;
}) {
  const { t, i18n } = useTranslation();
  const run = migration.record.steps[step];
  const progress = useProgress(step, run);
  const start = useStartCopyMutation(step);
  const stop = useStopCopyMutation(step);
  const [confirming, setConfirming] = useState(false);
  const slug = COPIES[step]?.slug;
  // The step a refusal sends the admin back to.
  const destinations = t(
    `settings.migration.step.${STEP_SLUGS.connect_target}.title`,
  );
  const line = (code = "") =>
    t(`settings.migration.${COPY_CODES[code] ?? "error.crashed"}`, {
      step: destinations,
    });
  const refusal = start.error?.response?.data?.detail?.code ?? "";
  const running = run?.status === "running";
  const [key, counts] = progress
    ? copyProgress(step, progress, i18n.language)
    : ["copy.starting", {}];
  // Whether this page watched the run, so it has an end to announce.
  const [followed, setFollowed] = useState(false);
  useEffect(() => {
    if (running) setFollowed(true);
  }, [running]);
  // The step's row shows the result. This says it too, to a screen reader that waited on the copy.
  const finished =
    followed && step === "copy_database" && state.state === "done"
      ? t("settings.migration.copyDb.done", {
          tables: run?.report?.tables_copied?.toLocaleString(i18n.language),
          rows: run?.report?.rows_copied?.toLocaleString(i18n.language),
        })
      : "";

  // The command's own words for a run that did not count.
  const said =
    run?.error?.message ??
    run?.report?.problems?.map((problem) => problem.message).join("\n");
  // A copy that ended in a step that waits again no longer counts, so it is history.
  const stale = state.state === "current" && Boolean(run);

  return (
    <div className="flex flex-col items-start gap-3">
      {/* One region for both states, so the end of a run is announced as well as its progress. */}
      <p
        role="status"
        className={running ? "text-sm text-muted-foreground" : "sr-only"}
      >
        {running ? t(`settings.migration.${key}`, counts) : finished}
      </p>
      {running ? (
        <>
          {stop.isError && (
            <p role="alert" className="text-sm text-destructive">
              {t("settings.migration.failed")}
            </p>
          )}
          <Button
            variant="outline"
            size="sm"
            loading={stop.isPending}
            onClick={() => setConfirming(true)}
            ignoreTitleCase
          >
            {t("settings.migration.check.stop")}
          </Button>
          <ConfirmationModal
            open={confirming}
            onClose={() => setConfirming(false)}
            onCancel={() => setConfirming(false)}
            title={t("settings.migration.copy.stopTitle")}
            cancelText={t("modal.cancelButton")}
            confirmationText={t("settings.migration.check.stop")}
            onConfirm={() => {
              setConfirming(false);
              stop.mutate(run.run_id);
            }}
            size="x-small"
          >
            <ConfirmationModal.Content>
              {t(`settings.migration.${slug}.stopBody`)}
            </ConfirmationModal.Content>
          </ConfirmationModal>
        </>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            {t(`settings.migration.${slug}.body`)}
          </p>
          {stale && (
            <p className="text-sm">{t("settings.migration.copy.stale")}</p>
          )}
          {state.state === "blocked" && (
            <div role="alert" className="flex flex-col gap-1 text-sm">
              <p className="text-destructive">{line(state.reason)}</p>
              {said && <Details text={said} />}
            </div>
          )}
          {start.isError && (
            <p role="alert" className="text-sm text-destructive">
              {refusal in COPY_CODES
                ? line(refusal)
                : t("settings.migration.failed")}
            </p>
          )}
          <Button
            className="w-full sm:w-fit"
            loading={start.isPending}
            onClick={() => start.mutate()}
            ignoreTitleCase
          >
            {run
              ? t("settings.migration.copy.again")
              : t(`settings.migration.step.${STEP_SLUGS[step]}.title`)}
          </Button>
        </>
      )}
    </div>
  );
}

/**
 * The last progress line of a run that is on. A run belongs to no page, so this one follows it from
 * the last line it saw: after a reload that is the first, and after a dropped connection the one it had got to.
 */
function useProgress(step: CopyStepId, run?: MigrationCopyRun) {
  const client = useQueryClient();
  const [progress, setProgress] = useState<CopyEvent>();
  const live = run?.status === "running" ? run.run_id : undefined;
  useEffect(() => {
    if (!live) return;
    setProgress(undefined);
    const controller = new AbortController();
    (async () => {
      let seq = 0;
      let over = false;
      while (!over && !controller.signal.aborted) {
        const refused = await followCopy({
          step,
          runId: live,
          after: seq,
          controller,
          onEvent: (event) => {
            seq = event.seq;
            if (event.event === "progress") setProgress(event);
            over ||= event.event === "end";
          },
        });
        // A run the server no longer has was started again from somewhere else.
        over ||= refused?.status === 404;
        if (!over)
          await new Promise((resolve) => setTimeout(resolve, RETRY_MS));
      }
      // The server writes down how a run ended the next time the record is read.
      if (!controller.signal.aborted)
        client.invalidateQueries({ queryKey: migrationKeys.all });
    })();
    return () => controller.abort();
  }, [step, live, client]);
  return progress;
}
